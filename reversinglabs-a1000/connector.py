from connectors.core.connector import Connector
from .utils import rl_generate_token
from .operations import upload_sample, get_report, re_analyze_sample

operations = {'upload_sample': upload_sample,
              'get_report': get_report,
              're_analyze_sample': re_analyze_sample
              }


class ReversingLabsA1000(Connector):

    def execute(self, config, operation, params, **kwargs):
        action = operations.get(operation)
        return action(config, params, **kwargs)

    def check_health(self, config):
        # Test server using provided config params.
        return rl_generate_token(config)
