""" Example usage of agent_core.Agent """
import asyncio
import logging

from agent_core import Agent
from agent_core.config import Config
#from ariespython import did

logging.getLogger().setLevel(logging.DEBUG)
logging.getLogger('indy').setLevel(logging.WARNING)

if __name__ == '__main__':
    logging.debug('Getting Event Loop')
    LOOP = asyncio.get_event_loop()

    logging.debug('Loading configuration from file')
    CONFIG = Config.from_file('config.sample.toml')
    logging.debug('Retrieved config: %s', CONFIG.__dict__)

    logging.debug('Creating Agent from config')
    AGENT = Agent.from_config(CONFIG)
    logging.debug('Agent created')

    AGENT.run()
