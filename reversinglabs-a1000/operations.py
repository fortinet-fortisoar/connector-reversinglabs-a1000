from connectors.core.connector import ConnectorError
from .utils import rl_generate_token, handle_input, create_batch, create_batch_for_upload_sample, itemgetter, find_hash, handle_file_hash


def upload_sample(config, operation_params, **kwargs):
    cyops_auth_info = {}
    rl_token = rl_generate_token(config)['token']
    env = kwargs.get('env')
    if 'request' not in env:
        raise ConnectorError('Missing authentication data from the execution env.')
    cyops_auth_info['host'] = env['request']['baseUri']
    cyops_auth_info['token'] = env['request']['headers']['authorization']
    file_iri_list = handle_input(operation_params.get('file_iri'))
    return create_batch_for_upload_sample(cyops_auth_info, file_iri_list, rl_token, config)


def _create_batch(config, operation_params, report=None):
    rl_token = rl_generate_token(config)['token']
    hash_list = handle_file_hash(operation_params['file_hash'])
    result = {'response': '', 'not_found_keys': ''}
    processed_hashes = list(map(itemgetter('hash_value'), find_hash(hash_list, rl_token, config)['results']))
    not_found_hashes = list(set(hash_list) - set(processed_hashes))
    if processed_hashes:
        result['response'] = create_batch(processed_hashes, rl_token, config, report)
    result['not_found_keys'] = not_found_hashes if not_found_hashes.__len__() is not 0 else ''
    return result


def get_report(config, operation_params, **kwargs):
    return _create_batch(config, operation_params, 'report')


def re_analyze_sample(config, operation_params, **kwargs):
    return _create_batch(config, operation_params)
