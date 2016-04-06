import urlparse

import requests
import logging
from website.project.model import Comment

from website import settings

logger = logging.getLogger(__name__)


def get_varnish_servers():
    #  TODO: this should get the varnish servers from HAProxy or a setting
    return settings.VARNISH_SERVERS

    #  fields_changed will eventually let us ban even more accurately
def get_bannable_urls(instance, fields_changed):
    bannable_urls = []
    parsed_absolute_url = {}

    for host in get_varnish_servers():
        # add instance url
        varnish_parsed_url = urlparse.urlparse(host)
        parsed_absolute_url = urlparse.urlparse(instance.absolute_api_v2_url)
        url_string = '{scheme}://{netloc}{path}.*'.format(scheme=varnish_parsed_url.scheme,
                                                          netloc=varnish_parsed_url.netloc,
                                                          path=parsed_absolute_url.path)
        bannable_urls.append(url_string)

        if isinstance(instance, Comment):
            parsed_target_url = urlparse.urlparse(instance.target.referent.absolute_api_v2_url)
            url_string = '{scheme}://{netloc}{path}.*'.format(scheme=varnish_parsed_url.scheme,
                                                              netloc=varnish_parsed_url.netloc,
                                                              path=parsed_target_url.path)
            bannable_urls.append(url_string)
            parsed_root_target_url = urlparse.urlparse(instance.root_target.referent.absolute_api_v2_url)
            url_string = '{scheme}://{netloc}{path}.*'.format(scheme=varnish_parsed_url.scheme,
                                                              netloc=varnish_parsed_url.netloc,
                                                              path=parsed_root_target_url.path)
            bannable_urls.append(url_string)

    return bannable_urls, parsed_absolute_url.hostname


def ban_url(instance, fields_changed):
    # TODO: Refactor; Pull url generation into postcommit_task handling so we only ban urls once per request
    timeout = 0.3  # 300ms timeout for bans
    if settings.ENABLE_VARNISH:
        bannable_urls, hostname = get_bannable_urls(instance, fields_changed)

        for url_to_ban in set(bannable_urls):
            try:
                response = requests.request('BAN', url_to_ban, timeout=timeout, headers=dict(
                    Host=hostname
                ))
            except Exception as ex:
                logger.error('Banning {} failed: {}'.format(
                    url_to_ban,
                    ex.message
                ))
            else:
                if not response.ok:
                    logger.error('Banning {} failed: {}'.format(
                        url_to_ban,
                        response.text
                    ))
                else:
                    logger.info('Banning {} succeeded'.format(
                        url_to_ban
                    ))
