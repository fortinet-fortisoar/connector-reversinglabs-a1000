import requests
import hashlib
import json

from operator import itemgetter
from connectors.core.connector import get_logger, ConnectorError
logger = get_logger('ReversingLabs-a1000')


def rl_generate_token(config):
    result = {'token': ''}
    server = 'https://{0}'.format(config.get('url'))
    token_url = '%s%s' % (server, '/api-token-auth/')
    try:
        payload = {'username': config.get('username'), 'password': config.get('password')}
        response = requests.post(token_url, data=payload, verify=False)
        if response.ok:
            result['token'] = json.loads(response.content.decode('utf-8'))['token']
            logger.info('generate_token(): Successfully generate token %s' % result['token'])
            return result
        else:
            raise ConnectorError('Invalid login credential/url status code %s' % response.status_code)
    except Exception as err:
        raise ConnectorError(err)


def get_file_contents_from_cyops(cyops_host, cyops_token, file_iri):
    url = '%s%s' % (cyops_host, file_iri)
    headers = {'authorization': cyops_token}
    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.ok:
            logger.info('get_file_contents_from_cyops(): Successfully read file %s from host %s' % (file_iri, cyops_host))
            return response.content
        elif response.status_code == 401:
            logger.error('request failed with 401 unauthorized. could be due to token expiry. get the new token.')
            auth_request_url = cyops_host + '/api/auth/token'
            payload = cyops_token.split(' ')[1]
            auth_reponse = requests.put(auth_request_url, data=json.dumps(payload), verify=False,
                                        timeout=30, headers={"Authorization": cyops_token})
            if auth_reponse.ok:
                auth_token_new = auth_reponse.json()['token']
                response = requests.get(url, verify=False, headers={'Authorization': auth_token_new})
                logger.info('Successfully get contents of file %s from CyOps Host %s' % (file_iri, cyops_host))
                return response.content
            else:
                logger.error('request failed with status code %s' % response.status_code)
                raise ConnectorError('request failed with status code %s' % response.status_code)
    except Exception as err:
        raise ConnectorError(err)


def calculate_sha1(file_data):
    try:
        sha1 = hashlib.sha1(file_data).hexdigest()
        logger.info('calculate_sha1(): SHA1 calculated')
        return sha1
    except Exception as e:
        raise ConnectorError('calculate_sha1(): %s' % str(e))


def handle_input(file_iri_list):
    if isinstance(file_iri_list, list):
        file_iri_list = list(set(list(filter(None, file_iri_list))))  # remove empty and duplicates
        if file_iri_list.__len__() is 0:
            raise ConnectorError('handle_input(): File iri list is empty %s' % file_iri_list)
        else:
            return file_iri_list
    else:
        raise ConnectorError('Provided input is invalid format %s' % file_iri_list)


def handle_file_hash(hashes):
        if isinstance(hashes, list):
            hash_list = hashes
        elif isinstance(hashes, bytes):
            hash_list = [hashes.decode('utf-8')]
        elif isinstance(hashes, str):
            hash_list = [hashes]
        else:
            raise ConnectorError('Provided input is invalid format %s' % hashes)
        hash_list = list(set(list(filter(None, hash_list))))  # remove empty and duplicates
        if len(hash_list) > 0:
            return hash_list
        else:
            raise ConnectorError('Provided input is empty')


def find_not_submit_samples(not_found_hash_details, hash_values, result, token, config):
    """
    Find not submitted samples from selected samples using cyops attachments and upload to reversing labs server.
    """
    not_found_hashes = []
    if not_found_hash_details:
        not_found_hashes = list(map(itemgetter('hash_value'), not_found_hash_details))
        not_submitted_samples = itemgetter(*not_found_hashes)(hash_values)
        not_submitted_samples = list(not_submitted_samples) if isinstance(not_submitted_samples,
                                                                              tuple) else [not_submitted_samples]
        curr_submit = submit_samples(not_submitted_samples, token, config)  # return dict of current submitted file
        result['submitted'].update(curr_submit['submitted_file'])  # {curr_submitted_hash: curr_submitted_file_iri}
        result['submit_failed'].update(curr_submit['submit_failed'])
    processed_hashes = list(set(hash_values.keys()) - set(not_found_hashes))
    if processed_hashes:
        pre_exist = itemgetter(*processed_hashes)(hash_values)
        pre_exist = list(pre_exist) if isinstance(pre_exist, tuple) else [pre_exist]
        pre_exist = list(map(lambda file_iri: file_iri[1], pre_exist))
        result['pre_exist'].update(dict(zip(processed_hashes, pre_exist)))


def submit_samples(post_data_file, token, config):
    result = {'submitted_file': {}, 'submit_failed': []}
    for file_data in post_data_file:
        files = {'file': file_data[0]}
        server = 'https://{0}'.format(config.get('url'))
        url = '%s%s' % (server, '/api/uploads/')
        headers = {'Authorization': 'Token  %s' % token}
        try:
            response = requests.post(url, files=files, headers=headers)
            if response.ok:
                data = json.loads(response.content.decode('utf-8'))
                result['submitted_file'][data['detail']['sha1']] = file_data[1]
            else:
                logger.error('Error:submit_samples(): status code %s' % response.status_code)
                result['submit_failed'].append(file_data[1])
        except Exception as e:
            logger.exception('Error:submit_samples() %s' % str(e))
            result['submit_failed'].append(file_data[1])
    return result


def find_hash(hash_values, token, config, not_found=None):
        data = {'hash_values': list(hash_values)}
        server = 'https://{0}'.format(config.get('url'))
        url = '%s%s' % (server, '/api/samples/status/')
        headers = {'Authorization': 'Token  %s' % token}
        if not_found is None:
            params = {'status': 'processed'}
        else:
            params = {'status': 'not_found'}
        try:
            response = requests.post(url, data=data, headers=headers, params=params, verify=False)
            if response.ok:
                return json.loads(response.content.decode('utf-8'))
            else:
                raise ConnectorError('found_hash(): status code %s message %s' % (response.status_code,
                                                                                  response.content))
        except Exception as e:
            raise ConnectorError('found_hash(): %s' % e)


def analyze_bulk(hashes, rl_token, config):
        data = {'hash_value': hashes, 'analysis': 'cloud'}
        server = 'https://{0}'.format(config.get('url'))
        url = '%s%s' % (server, '/api/samples/analyze_bulk/')
        headers = {'Authorization': 'Token  %s' % rl_token}
        try:
            response = requests.post(url, data=data, headers=headers)
            if response.ok:
                logger.info('analyze_bulk(): Successfully analyzed %s' % hashes)
                return json.loads(response.content.decode('utf-8'))
            else:
                raise ConnectorError('analyze_bulk(): status code %s message %s' % (response.status_code,
                                                                                    response.content))
        except Exception as e:
            raise ConnectorError('analyze_bulk(): %s' % str(e))


def create_batch_for_upload_sample(cyops_auth_info, file_iri_list, rl_token, config):
    batch_size = 5
    count = 0
    hash_values = dict()  # {'file_hash' : ['file_data', 'file_iri']}
    result = {'pre_exist': {}, 'submitted': {}, 'submit_failed': {}}
    for file_iri in file_iri_list:
        if count == batch_size:
            not_found_hash_details = find_hash(hash_values.keys(), rl_token, config, 'not found')['results']
            find_not_submit_samples(not_found_hash_details, hash_values, result, rl_token, config)
            count = 0
            hash_values = dict()
        file_data = []
        data = get_file_contents_from_cyops(cyops_auth_info['host'], cyops_auth_info['token'], file_iri)
        if data is not '':
            file_data.append(data)
            file_data.append(file_iri)
            file_hash = calculate_sha1(file_data[0])
            hash_values[file_hash] = file_data
        else:
            result[file_iri] = "File is empty"
        count += 1
    if count:
        not_found = find_hash(hash_values.keys(), rl_token, config, 'not found')['results']
        find_not_submit_samples(not_found, hash_values, result, rl_token, config)
    return result


def create_batch(hashes, rl_token, config, report=None):
        end_index = batch_size = 100
        start_index = 0
        result = []
        while start_index < len(hashes):
            hash_list = hashes[start_index: end_index]
            if hash_list:
                if report is None:
                    result.append(analyze_bulk(hash_list, rl_token, config))
                else:
                    result.append(fetch_report(hash_list, rl_token, config))
            start_index = end_index
            end_index += batch_size
        return result


def fetch_report(hashes, token, config):
        server = 'https://{0}'.format(config.get('url'))
        url = '%s%s' % (server, '/api/samples/list/')
        data = {'hash_values': hashes,
                'fields': ['sha1',
                           'threat_status',
                           'threat_level',
                           'threat_name',
                           'trust_factor',
                           'classification_origin',
                           'classification_reason',
                           'local_first_seen',
                           'local_last_seen'
                           ]
                }
        headers = {'Authorization': 'Token  %s' % token}
        try:
            response = requests.post(url, data=data, headers=headers)
            if response.ok:
                logger.info('fetch_report(): Successfully fetched reports %s' % hashes)
                return json.loads(response.content.decode('utf-8'))
            else:
                raise ConnectorError('fetch_report(): status code %s message %s' % (response.status_code,
                                                                                    response.content))
        except Exception as e:
            raise ConnectorError('fetch_report(): %s' % e)
