import toml


def load_config(config_file: str):
    """Load configuration from toml file."""
    return toml.load(config_file)['config']


def default():
    """Return a default config dictionary."""
    return {
        'host': 'localhost',
        'port': 3000,
        'endpoint': 'http://localhost:3000',
        'subject': {
            'endpoint': 'http://localhost:3001'
        },
        'features': []
    }
