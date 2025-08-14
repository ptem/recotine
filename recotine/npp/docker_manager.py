"""
Docker Manager for Recotine - handles Nicotine++ container lifecycle
"""

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any

from recotine.paths import PROJECT_ROOT

logger = logging.getLogger(__name__)


class DockerManager:
    """Manages Docker containers for Nicotine++"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.docker_config = config.get('docker', {})
        self.music_config = config.get('music', {})
        self.docker_dir = PROJECT_ROOT / '.npp'
        
    def _create_env_file(self) -> Path:
        """Create .env file from configuration"""
        env_path = self.docker_dir / '.env'
        
        env_content = f"""# Auto-generated Docker Environment Configuration
MUSIC_LIBRARY_PATH={self.music_config.get('library_path', '')}
"""
        
        with open(env_path, 'w') as f:
            f.write(env_content)
            
        logger.info(f"Created .env file at {env_path}")
        return env_path
    
    def _validate_paths(self) -> bool:
        """Validate required paths exist"""
        library_path = self.music_config.get('library_path')
        download_path = self.music_config.get('download_path')
        
        if not library_path or not os.path.exists(library_path):
            logger.error(f"Music library path not found: {library_path}")
            return False
            
        if download_path and not os.path.exists(download_path):
            logger.info(f"Creating download directory: {download_path}")
            os.makedirs(download_path, exist_ok=True)
        elif not download_path:
            logger.debug("Download path not configured, skipping validation")
                
        return True
    
    def _run_docker_compose(self, command: str) -> bool:
        """Run docker-compose command"""
        if not self._validate_paths():
            return False
            
        self._create_env_file()
        
        cmd = ['docker-compose', '-f', str(self.docker_dir / 'docker-compose.yaml'), '--env-file', '.env']
        cmd.extend(command.split())
        
        try:
            logger.info(f"Running: {' '.join(cmd)}")
            result = subprocess.run(cmd, cwd=self.docker_dir, check=True, 
                                  capture_output=True, text=True, encoding='utf-8', errors='replace')
            logger.info(f"Docker command succeeded: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Docker command failed: {e.stderr}")
            return False
    
    def start_nicotine(self) -> bool:
        """Start Nicotine++ container"""
        logger.info("Starting Nicotine++ container")
        return self._run_docker_compose('up -d')
    
    def stop_nicotine(self) -> bool:
        """Stop all Nicotine++ containers"""
        logger.info("Stopping Nicotine++ containers")
        return self._run_docker_compose('down')
    
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