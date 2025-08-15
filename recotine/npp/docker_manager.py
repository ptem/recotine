"""
Docker Manager for Recotine - handles Nicotine++ container lifecycle
"""

import configparser
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional

from recotine.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)

# Constants
DEFAULT_WEB_API_HOST = 'localhost'
DEFAULT_WEB_API_PORT = 7770
DEFAULT_WEB_API_MAX_SEARCHES = 10
DEFAULT_FORWARDED_PORT_TIMEOUT = 60
MANAGED_ENV_VARS = ['SHARE_LIBRARY_PATH', 'WIREGUARD_PRIVATE_KEY', 'SERVER_HOSTNAMES', 'WIREGUARD_ADDRESS', 'TZ']


class DockerManager:
    """Manages Docker containers for Nicotine++"""
    
    def __init__(self, config):
        """Initialize DockerManager with RecotineConfig object.
        
        Args:
            config: RecotineConfig instance
            
        Raises:
            ValueError: If config is not a RecotineConfig object
        """
        self.config = config
        self.docker_dir = PROJECT_ROOT / '.npp'
        
        # Validate config object type early
        if not hasattr(config, 'music_library_path'):
            raise ValueError(
                "DockerManager requires a RecotineConfig object. "
                "Raw dict configuration is no longer supported. "
                "Please use RecotineConfig from recotine.cfg.config instead."
            )
        
    def _create_env_file(self) -> Path:
        """Create or update .env file from configuration, preserving custom variables"""
        env_path = self.docker_dir / '.env'
        
        # Extract configuration values
        recotine_vars = {
            'SHARE_LIBRARY_PATH': self.config.npp_share_library_path or '',
            'WIREGUARD_PRIVATE_KEY': self.config.gluetun_wireguard_private_key or '',
            'SERVER_HOSTNAMES': self.config.gluetun_server_hostnames or '',
            'WIREGUARD_ADDRESS': self.config.gluetun_wireguard_address or '',
            'TZ': self.config.gluetun_tz or ''
        }
        
        return self._update_env_file(env_path, recotine_vars)
    
    def _update_env_file(self, env_path: Path, recotine_vars: Dict[str, str]) -> Path:
        """Update .env file while preserving custom user variables"""
        # Read existing file if it exists
        existing_lines = self._read_existing_env_file(env_path)
        
        # Process existing lines, updating only Recotine-managed variables
        updated_lines, recotine_vars_found = self._process_existing_env_lines(existing_lines, recotine_vars)
        
        # Add missing variables and header if needed
        missing_vars = set(recotine_vars.keys()) - recotine_vars_found
        if missing_vars or not existing_lines:
            self._add_header_and_missing_vars(updated_lines, existing_lines, missing_vars, recotine_vars)
        
        # Write the updated content
        with open(env_path, 'w', encoding='utf-8') as f:
            f.writelines(updated_lines)
            
        self._log_env_update(env_path, len(recotine_vars_found), len(missing_vars))
        return env_path
    
    def _read_existing_env_file(self, env_path: Path) -> list:
        """Read existing .env file lines, handling errors gracefully"""
        if not env_path.exists():
            return []
            
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                return f.readlines()
        except Exception as e:
            logger.warning(f"Could not read existing .env file: {e}, will create new one")
            return []
    
    def _process_existing_env_lines(self, existing_lines: list, recotine_vars: Dict[str, str]) -> tuple:
        """Process existing .env lines, updating Recotine variables and preserving custom ones"""
        updated_lines = []
        recotine_vars_found = set()
        
        for line in existing_lines:
            line = line.rstrip('\n\r')
            
            # Check if this line is a Recotine-managed variable
            recotine_var_name = self._get_recotine_var_name(line, recotine_vars)
            if recotine_var_name:
                # Update this Recotine variable
                updated_lines.append(f"{recotine_var_name}={recotine_vars[recotine_var_name]}\n")
                recotine_vars_found.add(recotine_var_name)
            else:
                # Preserve custom user variables and comments
                updated_lines.append(line + '\n')
        
        return updated_lines, recotine_vars_found
    
    def _get_recotine_var_name(self, line: str, recotine_vars: Dict[str, str]) -> Optional[str]:
        """Check if a line contains a Recotine-managed variable and return its name"""
        for var_name in recotine_vars:
            if line.startswith(f"{var_name}="):
                return var_name
        return None
    
    def _add_header_and_missing_vars(self, updated_lines: list, existing_lines: list, 
                                   missing_vars: set, recotine_vars: Dict[str, str]):
        """Add header for new installations and append missing variables"""
        # Add header if file didn't exist or doesn't have one
        if not existing_lines and not any('Auto-generated Docker Environment Configuration' in line for line in existing_lines):
            header_lines = self._generate_env_header()
            for i, header_line in enumerate(header_lines):
                updated_lines.insert(i, header_line)
        
        # Add missing variables in sorted order for consistency
        for var_name in sorted(missing_vars):
            updated_lines.append(f"{var_name}={recotine_vars[var_name]}\n")
    
    def _generate_env_header(self) -> list:
        """Generate header for new .env files"""
        return [
            "# Auto-generated Docker Environment Configuration\n",
            "#\n",
            "# The following variables will be automatically set to their associated values\n",
            "# from recotine.yaml when executing 'npp start' or 'npp restart':\n",
            "#   - SHARE_LIBRARY_PATH\n",
            "#   - WIREGUARD_PRIVATE_KEY\n", 
            "#   - SERVER_HOSTNAMES\n",
            "#   - WIREGUARD_ADDRESS\n",
            "#   - TZ\n",
            "#\n",
            "# All other lines will be untouched and preserved.\n",
            "# You can safely add your own custom environment variables.\n",
            "\n"
        ]
    
    def _log_env_update(self, env_path: Path, updated_count: int, added_count: int):
        """Log .env file update results"""
        logger.info(f"Updated .env file at {env_path} (updated {updated_count}, added {added_count} Recotine variables)")
    
    def _get_forwarded_port(self) -> Optional[tuple]:
        """Get the forwarded port from Gluetun's forwarded_port file if available"""
        forwarded_port_file = self.docker_dir / 'npp_data' / 'gluetun' / 'forwarded_port'
        
        try:
            if not forwarded_port_file.exists():
                logger.debug(f"Forwarded port file not found at {forwarded_port_file}")
                return None
                
            with open(forwarded_port_file, 'r', encoding='utf-8') as f:
                port_content = f.read().strip()
                
            if not port_content or not port_content.isdigit():
                logger.warning(f"Invalid port content in forwarded_port file: '{port_content}'")
                return None
                
            port = int(port_content)
            # logger.info(f"Using Gluetun forwarded port: {port}")
            return (port, port)  # Return as tuple (min, max) format expected by pynicotine
            
        except Exception as e:
            logger.warning(f"Failed to read forwarded port file: {e}")
            return None
    
    def _inject_pynicotine_config(self) -> bool:
        """Inject custom configuration values into pynicotine config file"""
        config_path = self.docker_dir / 'npp_data' / 'config' / 'config'
        
        if not config_path.exists():
            logger.debug(f"Pynicotine config file not found at {config_path}, skipping injection")
            return True
        
        try:
            parser = configparser.ConfigParser()
            parser.read(config_path, encoding='utf-8')
            
            injected_values = []
            
            # Inject web_api configuration
            self._inject_web_api_config(parser, injected_values)
            
            # Inject server configuration (including forwarded port)
            self._inject_server_config(parser, injected_values)
            
            # Inject userinfo configuration
            self._inject_userinfo_config(parser, injected_values)
            
            # Inject logging configuration
            self._inject_logging_config(parser, injected_values)
            
            # Write updated config
            with open(config_path, 'w', encoding='utf-8') as f:
                parser.write(f)
            
            # logger.info(f"Injected custom config values into pynicotine config: {'; '.join(injected_values)}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to inject pynicotine config: {e}")
            return False
    
    def _inject_web_api_config(self, parser: configparser.ConfigParser, injected_values: list):
        """Inject web API configuration into pynicotine config"""
        if not parser.has_section('web_api'):
            parser.add_section('web_api')
        
        # Get web_api values with fallbacks
        web_api_enable = self.config.npp_web_api_enable or True
        web_api_host = (self.config.npp_web_api_host or 
                       self.config.npp_api_host or 
                       DEFAULT_WEB_API_HOST)
        web_api_port = (self.config.npp_web_api_port or 
                       self.config.npp_api_port or 
                       DEFAULT_WEB_API_PORT)
        web_api_max_searches = (self.config.npp_web_api_max_simultaneous_searches or 
                               DEFAULT_WEB_API_MAX_SEARCHES)
        
        # Set web_api values
        parser.set('web_api', 'enable', str(web_api_enable))
        parser.set('web_api', 'local_ip', str(web_api_host))
        parser.set('web_api', 'local_port', str(web_api_port))
        parser.set('web_api', 'max_simultaneous_searches', str(web_api_max_searches))
        
        injected_values.append(f"web_api: enable={web_api_enable}, host={web_api_host}, port={web_api_port}, max_searches={web_api_max_searches}")
    
    def _inject_server_config(self, parser: configparser.ConfigParser, injected_values: list):
        """Inject server configuration into pynicotine config"""
        forwarded_port = self._get_forwarded_port()
        
        server_config = [
            ('server', self.config.npp_server),
            ('login', self.config.npp_login),
            ('passw', self.config.npp_password),
            ('portrange', forwarded_port),
            ('upnp', self.config.npp_upnp),
            ('upnp_interval', self.config.npp_upnp_interval)
        ]
        
        server_injected = self._inject_config_section('server', server_config, parser)
        if server_injected:
            injected_values.append(f"server: {', '.join(server_injected)}")
    
    def _inject_userinfo_config(self, parser: configparser.ConfigParser, injected_values: list):
        """Inject userinfo configuration into pynicotine config"""
        userinfo_config = [
            ('descr', self.config.npp_user_description),
            ('pic', self.config.npp_user_picture)
        ]
        
        userinfo_injected = self._inject_config_section('userinfo', userinfo_config, parser)
        if userinfo_injected:
            injected_values.append(f"userinfo: {', '.join(userinfo_injected)}")
    
    def _inject_logging_config(self, parser: configparser.ConfigParser, injected_values: list):
        """Inject logging configuration into pynicotine config"""
        logging_config = [
            ('debug', self.config.npp_debug),
            ('debugmodes', self.config.npp_debug_modes)
        ]
        
        logging_injected = self._inject_config_section('logging', logging_config, parser)
        if logging_injected:
            injected_values.append(f"logging: {', '.join(logging_injected)}")
    
    def _inject_config_section(self, section_name: str, config_items: list, 
                              parser: configparser.ConfigParser) -> list:
        """Generic helper to inject configuration section"""
        injected = []
        
        for option, value in config_items:
            if value is not None:
                if not parser.has_section(section_name):
                    parser.add_section(section_name)
                parser.set(section_name, option, str(value))
                injected.append(f"{option}={value}")
        
        return injected
    
    def _validate_paths(self) -> bool:
        """Validate required paths exist"""
        library_path = str(self.config.music_library_path)
        download_path = str(self.config.music_output_path)
        
        if not library_path or not os.path.exists(library_path):
            logger.error(f"Music library path not found: {library_path}")
            return False
            
        if download_path and not os.path.exists(download_path):
            logger.info(f"Creating download directory: {download_path}")
            os.makedirs(download_path, exist_ok=True)
        elif not download_path:
            logger.debug("Download path not configured, skipping validation")
                
        return True
    
    def _run_docker_compose(self, command: str, update_env: bool = True) -> bool:
        """Run docker-compose command
        
        Args:
            command: The docker-compose command to run
            update_env: Whether to update the .env file before running the command
        """
        if not self._validate_paths():
            return False
            
        if update_env:
            self._create_env_file()
        
        cmd = ['docker-compose', '-f', str(self.docker_dir / 'docker-compose.yaml'), '--env-file', '.env']
        cmd.extend(command.split())
        
        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=self.docker_dir, check=True, 
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            if result.stdout:
                logger.info(f"Docker command succeeded: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker command failed: {e.stderr}")
            return False
    
    def _wait_for_forwarded_port(self, timeout: int = DEFAULT_FORWARDED_PORT_TIMEOUT) -> bool:
        """Wait for Gluetun to create the forwarded_port file.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if forwarded_port file is created, False if timeout
        """
        forwarded_port_file = self.docker_dir / 'npp_data' / 'gluetun' / 'forwarded_port'
        
        logger.info("Waiting for Gluetun to create forwarded_port file...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if forwarded_port_file.exists():
                # File exists, but let's make sure it has content
                try:
                    with open(forwarded_port_file, 'r', encoding='utf-8') as f:
                        port_content = f.read().strip()
                    if port_content and port_content.isdigit():
                        logger.info(f"Forwarded port from VPN provider: {port_content}")
                        return True
                except Exception as e:
                    logger.debug(f"Error reading forwarded_port file: {e}")
            
            time.sleep(1)  # Check every second
        
        logger.warning(f"Timeout waiting for forwarded_port file after {timeout} seconds")
        return False
    
    def start_nicotine(self) -> bool:
        """Start Nicotine++ container"""
        
        # Start the containers first
        if not self._run_docker_compose('up -d'):
            return False
        
        # Wait for Gluetun to create the forwarded_port file
        if self._wait_for_forwarded_port():
            # logger.info("Gluetun forwarded port found, Starting Nicotine++ container...")
            # Inject configuration now that we have the forwarded port
            logger.info("Injecting configuration to ./npp/npp_data/config/config...")
            if not self._inject_pynicotine_config():
                logger.warning("Failed to inject pynicotine config!")
        else:
            logger.warning("Proceeding without forwarded port - config may have incorrect portrange!")

        return True
    
    def stop_nicotine(self) -> bool:
        """Stop all Nicotine++ containers"""
        logger.info("Stopping Nicotine++ containers")
        return self._run_docker_compose('down', update_env=False)
    
    def restart_nicotine(self) -> bool:
        """Restart Nicotine++ containers"""
        logger.info("Restarting Nicotine++ containers")
        if self.stop_nicotine():
            time.sleep(2)  # Brief pause
            return self.start_nicotine()
        return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of Docker containers"""
        try:
            result = subprocess.run(['docker-compose', '-f', str(self.docker_dir / 'docker-compose.yaml'), '--env-file', '.env', 'ps'],
                                  cwd=self.docker_dir, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
            return {
                'running': 'Up' in result.stdout,
                'output': result.stdout
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get container status: {e.stderr}")
            return {'running': False, 'error': str(e)}
    
    
    def get_logs(self, service: str = None, lines: int = 50) -> str:
        """Get logs from Docker containers"""
        cmd = ['docker-compose', '-f', str(self.docker_dir / 'docker-compose.yaml'), '--env-file', '.env', 'logs']
        
        if lines:
            cmd.extend(['--tail', str(lines)])
            
        if service:
            cmd.append(service)
            
        try:
            result = subprocess.run(cmd, cwd=self.docker_dir, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to get logs: {e.stderr}")
            return f"Error getting logs: {e.stderr}"
    
    def exec_command(self, command: str, service: str = "nicotine") -> str:
        """Execute command in Docker container"""
        self._create_env_file()
        
        cmd = ['docker-compose', '-f', str(self.docker_dir / 'docker-compose.yaml'), '--env-file', '.env', 'exec', '-T', service]
        cmd.extend(command.split())
        
        try:
            logger.info(f"Executing in container: {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=self.docker_dir, capture_output=True, text=True, encoding='utf-8', errors='replace', check=True)
            return result.stdout
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to execute command: {e.stderr}")
            return f"Error executing command: {e.stderr}"