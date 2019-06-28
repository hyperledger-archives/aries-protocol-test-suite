""" Example usage of agent_core.Agent """
import asyncio
import logging

from agent_core import Agent
from agent_core import CliAgentConfig
#from ariespython import did

if __name__ == '__main__':
    print('Loading configuration')
    CONFIG = CliAgentConfig.from_args()
    AGENT = Agent.from_config(CONFIG)
    AGENT.run()
