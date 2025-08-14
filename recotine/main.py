#!/usr/bin/env python3
"""Recotine - Music recommendation and download automation tool."""

import subprocess
import sys
import urllib.request
from pathlib import Path

import click

from recotine.api.lastfm_api import create_lastfm_client
from recotine.api.listenbrainz_api import create_listenbrainz_client
from recotine.cfg.config import load_config
from recotine.cfg.template_generator import regenerate_template
from recotine.npp.docker_manager import DockerManager


def _print_compact_command_tree(ctx, command, prefix="", is_last=True, max_cmd_width=20):
    """Recursively print compact command tree with descriptions aligned on same line."""
    # Get the command name
    if hasattr(command, 'name') and command.name:
        cmd_name = command.name
    else:
        cmd_name = getattr(command, '_name', 'cli')
    
    # Print current command with tree formatting and description on same line
    tree_char = "└── " if is_last else "├── "
    cmd_display = f"{prefix}{tree_char}{cmd_name}"
    
    # Get command help/description if available
    help_text = ""
    if hasattr(command, 'get_short_help_str'):
        help_text = command.get_short_help_str(limit=80)
    
    if help_text:
        # Calculate padding to align descriptions
        padding = max_cmd_width - len(cmd_display) + 2
        if padding < 2:
            padding = 2
        click.echo(f"{cmd_display}{' ' * padding}{help_text}")
    else:
        click.echo(cmd_display)
    
    # If this is a group, recursively print its subcommands
    if isinstance(command, click.Group):
        subcommands = []
        if hasattr(command, 'commands'):
            subcommands = list(command.commands.values())
        elif hasattr(command, 'list_commands'):
            cmd_names = command.list_commands(ctx)
            subcommands = [command.get_command(ctx, name) for name in cmd_names if command.get_command(ctx, name)]
        
        if subcommands:
            # Sort subcommands by name for consistent output
            subcommands.sort(key=lambda x: getattr(x, 'name', ''))
            
            new_prefix = prefix + ("    " if is_last else "│   ")
            for i, subcmd in enumerate(subcommands):
                is_last_sub = (i == len(subcommands) - 1)
                _print_compact_command_tree(ctx, subcmd, new_prefix, is_last_sub, max_cmd_width)


class CustomGroup(click.Group):
    """Custom Click group that shows commands in tree format by default."""
    
    def format_commands(self, ctx, formatter):
        """Override to show tree structure instead of standard help."""
        # Show the main description first
        click.echo("Recotine - Music recommendation and download automation tool.")
        click.echo()
        click.echo("Fetches recommendations from Last.fm and ListenBrainz, downloads tracks")
        click.echo("via Nicotine++, and manages your music library with Navidrome.")
        click.echo()
        click.echo("Commands:")
        
        # Calculate max width for alignment
        max_width = self._calculate_max_command_width(ctx, self, "")
        
        # Print the tree structure
        _print_compact_command_tree(ctx, self, "", True, max_width)
        
        click.echo()
        click.echo("Use 'main.py COMMAND --help' for more information on a command.")
    
    def _calculate_max_command_width(self, ctx, command, prefix, depth=0):
        """Calculate the maximum width needed for command display."""
        max_width = 0
        
        if hasattr(command, 'commands'):
            subcommands = list(command.commands.values())
        elif hasattr(command, 'list_commands'):
            cmd_names = command.list_commands(ctx)
            subcommands = [command.get_command(ctx, name) for name in cmd_names if command.get_command(ctx, name)]
        else:
            return 0
        
        for i, subcmd in enumerate(subcommands):
            is_last = (i == len(subcommands) - 1)
            tree_char = "└── " if is_last else "├── "
            cmd_name = getattr(subcmd, 'name', 'unknown')
            cmd_display = f"{prefix}{tree_char}{cmd_name}"
            max_width = max(max_width, len(cmd_display))
            
            if isinstance(subcmd, click.Group) and depth < 3:  # Limit recursion depth
                new_prefix = prefix + ("    " if is_last else "│   ")
                sub_width = self._calculate_max_command_width(ctx, subcmd, new_prefix, depth + 1)
                max_width = max(max_width, sub_width)
        
        return max_width


@click.group(cls=CustomGroup)
@click.pass_context
def cli(ctx):
    # """Recotine - Music recommendation and download automation tool.
    #
    # Fetches recommendations from Last.fm and ListenBrainz, downloads tracks
    # via Nicotine++, and manages your music library with Navidrome.
    # """
    ctx.ensure_object(dict)
    try:
        ctx.obj['config'] = load_config()
    except (FileNotFoundError, ValueError) as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)


@cli.group()
def fetch():
    """Fetch recommendations from various sources."""
    pass


@fetch.command("lastfm")
@click.pass_context
def fetch_lastfm_cmd(ctx):
    """Fetch Last.fm recommendations and save to file."""
    config = ctx.obj['config']
    
    try:
        client = create_lastfm_client(config)
        file_path = client.fetch_and_save_unified_recommendations()
        click.echo(f"✅ Last.fm recommendations saved to: {file_path}")
    except Exception as e:
        click.echo(f"❌ Failed to fetch Last.fm recommendations: {e}", err=True)
        sys.exit(1)


@fetch.command("listenbrainz")
@click.option('--sp', '--source-patch', 
              help='Filter by specific source patch (e.g., weekly-exploration, weekly-jams)')
@click.pass_context
def fetch_listenbrainz_cmd(ctx, sp):
    """Fetch ListenBrainz createdfor playlists and save tracks to text files (one per playlist)."""
    config = ctx.obj['config']
    
    try:
        client = create_listenbrainz_client(config)
        
        # Fetch createdfor playlists (all or filtered by source_patch)
        saved_files = client.fetch_and_save_recommendations(source_patch=sp)

        if saved_files:
            if sp:
                click.echo(f"✅ ListenBrainz playlists with source patch '{sp}' saved:")
            else:
                click.echo("✅ ListenBrainz playlists saved:")
            for file_path in saved_files:
                click.echo(f"   {file_path}")
        else:
            if sp:
                click.echo(f"⚠️  No ListenBrainz playlists found with source patch '{sp}'")
            else:
                click.echo("⚠️  No ListenBrainz playlists found in createdfor")
            
    except Exception as e:
        click.echo(f"❌ Failed to fetch ListenBrainz playlists: {e}", err=True)
        sys.exit(1)


@fetch.command("all")
@click.pass_context
def fetch_all_cmd(ctx):
    """Fetch recommendations from both Last.fm and ListenBrainz."""
    click.echo("🎵 Fetching recommendations from all sources...")
    
    # Fetch Last.fm
    ctx.invoke(fetch_lastfm_cmd)
    
    # Fetch ListenBrainz
    ctx.invoke(fetch_listenbrainz_cmd)
    
    click.echo("✨ All recommendations fetched successfully!")




@cli.group()
def npp():
    """Manage Nicotine++ containers."""
    pass


@npp.command("start")
@click.pass_context
def npp_start_cmd(ctx):
    """Start Nicotine++ container."""
    config = ctx.obj['config']
    docker_manager = DockerManager(config.raw_config)
    
    click.echo("🚀 Starting Nicotine++ container...")
    
    if docker_manager.start_nicotine():
        click.echo("✅ Nicotine++ container started successfully!")
    else:
        click.echo("❌ Failed to start Nicotine++ container", err=True)
        sys.exit(1)


@npp.command("stop")
@click.pass_context
def npp_stop_cmd(ctx):
    """Stop Nicotine++ containers."""
    config = ctx.obj['config']
    docker_manager = DockerManager(config.raw_config)
    
    click.echo("🛑 Stopping Nicotine++ containers...")
    
    if docker_manager.stop_nicotine():
        click.echo("✅ Nicotine++ containers stopped successfully!")
    else:
        click.echo("❌ Failed to stop Nicotine++ containers", err=True)
        sys.exit(1)


@npp.command("restart")
@click.pass_context
def npp_restart_cmd(ctx):
    """Restart Nicotine++ containers."""
    config = ctx.obj['config']
    docker_manager = DockerManager(config.raw_config)
    
    click.echo("🔄 Restarting Nicotine++ containers...")
    
    if docker_manager.restart_nicotine():
        click.echo("✅ Nicotine++ containers restarted successfully!")
    else:
        click.echo("❌ Failed to restart Nicotine++ containers", err=True)
        sys.exit(1)


@npp.command("status")
@click.pass_context
def npp_status_cmd(ctx):
    """Show Nicotine++ container status."""
    config = ctx.obj['config']
    docker_manager = DockerManager(config.raw_config)
    
    click.echo("📊 Nicotine++ Container Status:")
    status = docker_manager.get_status()
    
    if status.get('running'):
        click.echo("✅ Containers are running")
    else:
        click.echo("❌ Containers are not running")
        
    if 'output' in status:
        click.echo("\nContainer Details:")
        click.echo(status['output'])


@npp.command("logs")
@click.option('--service', '-s', help='Specific service to get logs from')
@click.option('--lines', '-n', default=50, help='Number of log lines to display')
@click.pass_context
def npp_logs_cmd(ctx, service, lines):
    """Show Nicotine++ container logs."""
    config = ctx.obj['config']
    docker_manager = DockerManager(config.raw_config)
    
    click.echo(f"📜 Nicotine++ Container Logs (last {lines} lines):")
    logs = docker_manager.get_logs(service, lines)
    click.echo(logs)


@npp.command("exec")
@click.argument('command', required=True)
@click.option('--service', '-s', default='nicotine', help='Service to execute command in')
@click.pass_context
def npp_exec_cmd(ctx, command, service):
    """Execute command in Nicotine++ container."""
    config = ctx.obj['config']
    docker_manager = DockerManager(config.raw_config)
    
    click.echo(f"🖥️  Executing '{command}' in {service} container:")
    output = docker_manager.exec_command(command, service)
    click.echo(output)


@npp.group("setup")
def setup_npp():
    """Set up Nicotine++ components."""
    pass


@setup_npp.command("install")
@click.pass_context
def setup_npp_install(ctx):
    """Install Nicotine++ by cloning git repository to .npp directory and apply configuration."""
    target_path = Path("../.npp")
    repo_url = "https://github.com/pachiclana/nicotine-plus-plus.git"
    
    if target_path.exists():
        click.echo("⚠️  .npp directory already exists!")
        click.echo("⚠️  This will overwrite the existing Nicotine++ container setup!")
        if not click.confirm("Are you sure you want to continue?"):
            click.echo("Setup cancelled.")
            return
        if not click.confirm("This will DELETE the current .npp directory. Continue?"):
            click.echo("Setup cancelled.")
            return
        
        # Remove existing directory with Windows-compatible error handling
        import shutil
        import stat
        import os
        
        def handle_remove_readonly(func, path, exc):
            """Error handler for Windows readonly files."""
            if os.path.exists(path):
                os.chmod(path, stat.S_IWRITE)
                func(path)
        
        try:
            click.echo("🗑️  Removing existing .npp directory...")
            shutil.rmtree(target_path, onerror=handle_remove_readonly)
            click.echo("✅ Existing .npp directory removed successfully")
        except Exception as e:
            click.echo(f"❌ Failed to remove existing directory: {e}", err=True)
            click.echo("Please manually delete the .npp directory and try again.")
            sys.exit(1)
    
    click.echo("📦 Cloning Nicotine++ repository...")
    click.echo(f"   Repository: {repo_url}")
    click.echo(f"   Target: {target_path}")
    
    try:
        result = subprocess.run(
            ["git", "clone", repo_url, str(target_path)],
            capture_output=True,
            text=True,
            check=True
        )
        click.echo("✅ Nicotine++ repository cloned successfully!")
        
        # Apply configuration automatically after successful clone
        click.echo("🔧 Applying configuration settings...")
        _apply_config_internal(ctx, skip_fetch=True)
        
        # Show usage instructions
        click.echo("\n🎉 Nicotine++ installation complete!")
        click.echo("📋 Here's how to manage your Nicotine++ Docker container:")
        click.echo("")
        click.echo("  🚀 Start the container:")
        click.echo("     ./recotine npp start")
        click.echo("")
        click.echo("  📊 Check container status:")
        click.echo("     ./recotine npp status")
        click.echo("")
        click.echo("  📜 View container logs:")
        click.echo("     ./recotine npp logs")
        click.echo("     ./recotine npp logs --lines 100  # Show more lines")
        click.echo("")
        click.echo("  🖥️  Execute commands in container:")
        click.echo("     ./recotine npp exec \"ls\"")
        click.echo("     ./recotine npp exec \"ls /data/nicotine/uploads\"  # Check to see if your share is mounted!")
        click.echo("")
        click.echo("  🔄 Restart container:")
        click.echo("     ./recotine npp restart")
        click.echo("")
        click.echo("  🛑 Stop container:")
        click.echo("     ./recotine npp stop")
        click.echo("")
        click.echo("💡 Start with './recotine npp start' to begin using Nicotine++!")
        
    except subprocess.CalledProcessError as e:
        click.echo(f"❌ Failed to clone repository: {e}", err=True)
        click.echo("Make sure git is installed and you have internet access.")
        sys.exit(1)
    except FileNotFoundError:
        click.echo("❌ Git not found! Please install git first.", err=True)
        sys.exit(1)



def _apply_config_internal(ctx, skip_fetch=False):
    """Internal function to apply config settings from npp section to .npp/docker-compose.yaml."""
    config = ctx.obj["config"]
    docker_compose_path = Path("../.npp/docker-compose.yaml")
    
    # Ensure .npp directory exists
    docker_compose_path.parent.mkdir(exist_ok=True)
    
    # Get npp and music config sections
    npp_config = config.raw_config.get("npp", {})
    music_config = config.raw_config.get("music", {})
    
    network_mode = npp_config.get("network_mode", "host")
    use_music_library = npp_config.get("use_music_library", False)
    library_path = music_config.get("library_path", "")
    
    click.echo(f"🔧 Applying config settings to {docker_compose_path}")
    
    if skip_fetch:
        # Use existing docker-compose.yaml from the cloned repository
        if not docker_compose_path.exists():
            click.echo("❌ No docker-compose.yaml found after clone!", err=True)
            sys.exit(1)
        
        with open(docker_compose_path, "r") as f:
            lines = f.readlines()
    else:
        # Fetch fresh docker-compose.yaml from GitHub
        docker_compose_url = "https://raw.githubusercontent.com/pachiclana/nicotine-plus-plus/master/docker-compose.yaml"
        click.echo("📥 Fetching fresh docker-compose.yaml from GitHub...")
        
        try:
            with urllib.request.urlopen(docker_compose_url) as response:
                docker_compose_content = response.read().decode('utf-8')
            
            # Write the fresh content to the local file first
            with open(docker_compose_path, "w") as f:
                f.write(docker_compose_content)
            
            click.echo("✅ Successfully fetched fresh docker-compose.yaml")
            lines = docker_compose_content.splitlines(keepends=True)
            
        except Exception as e:
            click.echo(f"⚠️  Failed to fetch from GitHub: {e}", err=True)
            click.echo("🔄 Using existing local docker-compose.yaml if available...")
            
            if not docker_compose_path.exists():
                click.echo("❌ No local docker-compose.yaml found and GitHub fetch failed!", err=True)
                click.echo("Run './recotine npp setup install' first to clone the repository.")
                sys.exit(1)
            
            # Read current docker-compose.yaml as fallback
            with open(docker_compose_path, "r") as f:
                lines = f.readlines()
    
    # Apply modifications
    modified_lines = []
    network_mode_added = False
    
    for line in lines:
        # Apply network_mode setting - replace existing or add after build line
        if line.strip().startswith("network_mode:"):
            modified_lines.append(f"    network_mode: {network_mode}\n")
            click.echo(f"✅ Set network_mode to: {network_mode}")
            network_mode_added = True
        # Add network_mode after build line if not already present
        elif line.strip().startswith("build:") and not network_mode_added:
            modified_lines.append(line)
            modified_lines.append(f"    network_mode: {network_mode}\n")
            click.echo(f"✅ Added network_mode: {network_mode}")
            network_mode_added = True
            continue
        # Apply volume changes for uploads if use_music_library is true
        elif ":/data/nicotine/uploads" in line and use_music_library:
            # Replace the uploads volume with environment variable
            indent = line[:line.index("-")]  # Preserve indentation
            modified_lines.append(f"{indent}- ${{MUSIC_LIBRARY_PATH}}:/data/nicotine/uploads\n")
            click.echo("✅ Changed uploads volume to use ${MUSIC_LIBRARY_PATH} environment variable")
        else:
            modified_lines.append(line)
    
    # Write the modified content back
    with open(docker_compose_path, "w") as f:
        f.writelines(modified_lines)
    
    # Create .env file
    env_path = Path("../.npp/.env")
    env_content = f"""# Auto-generated Docker Environment Configuration
MUSIC_LIBRARY_PATH={library_path}
"""
    
    with open(env_path, "w") as f:
        f.write(env_content)
    
    click.echo(f"✅ Created .env file at {env_path}")
    click.echo("🎉 Configuration applied successfully!")
    if not skip_fetch:
        click.echo("🐳 You can now use './recotine npp restart' to apply changes")


@setup_npp.command("apply-config")
@click.pass_context
def setup_npp_apply_config(ctx):
    """Apply config settings from npp section to .npp/docker-compose.yaml."""
    _apply_config_internal(ctx, skip_fetch=False)


@cli.group()
def config():
    """Manage configuration files."""
    pass


@config.command("regenerate")
@click.pass_context
def config_regenerate_cmd(ctx):
    """Regenerate the configuration template using template_generator."""
    try:
        click.echo("🔄 Regenerating configuration template...")
        
        # Call the regenerate_template function
        template_path = regenerate_template()
        
        click.echo(f"✅ Template regenerated successfully: {template_path}")
        click.echo("💡 Copy this template to config/recotine.yaml and customize it with your settings.")
        
    except Exception as e:
        click.echo(f"❌ Failed to regenerate template: {e}", err=True)
        sys.exit(1)



def main():
    """Main entry point for Recotine."""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        click.echo(f"💥 Unexpected error: {e}", err=True)
        sys.exit(1)


if __name__ == '__main__':
    main()