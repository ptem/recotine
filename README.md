# Recotine

An in-development Python CLI tool for music discovery and acquisition for Navidrome.
<br>
## Primary Features
- **Music Discovery**: Utilizes the Last.fm and ListenBrainz APIs to fetch music recommendations.
- **P2P Search & Download**: Automated track acquisition via a fork of Nicotine++, a containerized headless fork of Nicotine+, a client for Soulseek. 
- **VPN Support**: Gluetun VPN container for privacy with automatic port forward updating in Nicotine++ for ProtonVPN/Wireguard.
- **Navidrome Integration (In development)**:
  - Create Navidrome "Discover Weekly"-type playlists from music recommendations.
  - Tracks which are found in your library are utilized instead of acquiring through P2P methods.
  - New tracks are automatically tagged. When the playlist is refreshed, tagged tracks that are either unliked or rated below a threshold are removed from your library.
  - Kept tracks will remain in your library, to be organized later.

## Requirements

- Python 3.7+
- Docker, Docker Compose, and Git
- ProtonVPN (tested) or similar VPN service with Wireguard support.
- Last.fm, ListenBrainz api keys and user tokens.

## Installation

1. **Clone the repository and install dependencies**:
   ```bash
   git clone https://github.com/ptem/nicotine-plus-plus.git
   cd recotine
   chmod +x rec
   pip install -r requirements.txt
   ```

## Quick Start
You can explore the command structure with `./rec` or `python -m recotine`. 

### 1. Install Nicotine++
```bash
./rec setup npp install
```
This clones the Nicotine++ repository to `.npp/` and sets up the Docker configuration.

### 2. Configure Recotine and Start Nicotine++/Gluetun containers
```bash
# Generate configuration template
./rec config regenerate

# Copy and edit the configuration
cp config/templates/_template_recotine.yaml config/recotine.yaml
# Edit config/recotine.yaml with your API keys and preferences
# Applicable .env variables for the docker-compose will be copied from config/recotine.yaml at runtime.
# Applicable soulseek/nicotine+/nicotine++ settings will be injected into their config at runtime to manage their quirks.

./rec npp start
```


### 4. Fetch Music Recommendations
```bash
# Fetch from all sources
./rec fetch all

# Or fetch from specific sources
./rec fetch lastfm
./rec fetch listenbrainz --sp weekly-jams
```

## Configuration

### API Credentials

You'll need credentials from:

- **[Last.fm](https://www.last.fm/api)**: Requires username, api key & secret, and session key.
- **[ListenBrainz](https://listenbrainz.org/settings/)**: Requires username and user token.
- **Wireguard**: Get wireguard private keys and server hostnames, e.g. through [ProtonVPN](https://protonvpn.com/support/wireguard-configurations/).

### Configuration File

Edit `config/recotine.yaml` with your settings:

```yaml
# Last.fm API Configuration
lastfm:
  username: "your_lastfm_username"
  api_key: "your_lastfm_api_key"
  api_secret: "your_lastfm_api_secret"
  session_key: ""  # Will be populated automatically after authentication

# ListenBrainz Configuration
listenbrainz:
  username: "your_listenbrainz_username"
  user_token: "your_listenbrainz_user_token"

# Music Library Configuration
music:
  library_path: "/path/to/your/music/library"               # Path to your music SHARE library for nicotine++. Please share to others if downloading.
  output_path: "/path/to/navidrome/temp/library"            # Where finished playlist tracks (that aren't in your library already) are placed

# Navidrome/Subsonic Configuration
navidrome:
  url: "http://your-navidrome-server:4533"
  username: "your_navidrome_username"
  password: "your_navidrome_password"

# Gluetun VPN Docker Configuration
gluetun:
  wireguard_private_key: "wireguardprivkey"
  server_hostnames: "node-us-999.protonvpn.net"
  wireguard_address: "10.x.y.z/99"
  tz: "America/New_York"
```

## Commands Reference

### Music Recommendations
```bash
# Fetch all recommendations
./rec fetch all

# Fetch Last.fm recommendations
./rec fetch lastfm

# Fetch ListenBrainz recommendations
./rec fetch listenbrainz --sp weekly-jams
./rec fetch listenbrainz --sp weekly-exploration
```

### Nicotine++ Container Management
```bash
# Start the container
./rec npp start

# Stop the container
./rec npp stop

# Restart the container
./rec npp restart

# Check container status
./rec npp status

# View container logs
./rec npp logs
./rec npp logs --lines 100

# Execute commands in container
./rec npp exec "ls /data/nicotine"
```

## Audio Quality Settings

Recotine supports similar quality filtering to Nicotine++:

- **Format preferences**: Specify allowed formats when searching (MP3, FLAC, OGG, M4A, WMA, etc.)
- **Bitrate control**: Set minimum/maximum bitrates
- **Lossless preference**: Prioritize FLAC/other lossless formats
- **File size limits**: Control maximum download sizes
- **Search strategies**: Multiple fallback query formats

## File Structure

```
recotine/
├── recotine/              # Main Python package
│   ├── api/              # API clients (Last.fm, ListenBrainz)
│   ├── cfg/              # Configuration management
│   └── npp/              # Nicotine++ Docker management
├── config/               # Configuration files
│   └── templates/        # Configuration templates
├── recs/                 # Downloaded recommendations (JSON)
├── .npp/                # Nicotine++ installation (created by setup)
├── rec                   # CLI script (Unix)
├── rec.bat              # CLI script (Windows)
└── requirements.txt      # Python dependencies
```

## Troubleshooting

### Container Issues
- Ensure Docker is running
- Check logs: `./rec npp logs`
- Verify configuration paths exist

### Download Issues
- Verify VPN connection if using Gluetun
- Check Nicotine++ container status
- Adjust search preferences in configuration


## Disclaimer

This tool is for educational purposes. Ensure you comply with your local laws and respect artists' rights when downloading music. Please support artists through the platforms they provide. Fuck streaming services.