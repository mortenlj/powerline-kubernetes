# vim:fileencoding=utf-8:noet:tabstop=4:softtabstop=4:shiftwidth=4:expandtab:
import os
import yaml
from powerline.theme import requires_segment_info
from powerline.segments import Segment, with_docstring
from kubernetes.config import kube_config
import kubernetes.client as kubernetes_client
from kubernetes.client.rest import ApiException
import time

_KUBERNETES = u'\U00002388 '


@requires_segment_info
class KubernetesSegment(Segment):

    def kube_logo(self, color):
        return {'contents': _KUBERNETES, 'highlight_groups': [color], 'divider_highlight_group': 'kubernetes:divider'}

    def build_segments(self, context, namespace):
        alert = (context in self.alerts or namespace in self.alerts or context + ':' + namespace in self.alerts)
        segments = []

        if self.show_cluster:
            color = 'kubernetes_cluster:alert' if alert else 'kubernetes_cluster'
            if self.show_kube_logo:
                segments.append(self.kube_logo(color))

            segments.append({
                'contents': context,
                'highlight_groups': [color],
                'divider_highlight_group': 'kubernetes:divider'
            })

        if self.show_namespace:
            color = 'kubernetes_namespace:alert' if alert else 'kubernetes_namespace'

            if namespace != 'default' or self.show_default_namespace:
                if not self.show_cluster and self.show_kube_logo:
                    segments.append(self.kube_logo(color))

                segments.append({
                    'contents': namespace,
                    'highlight_groups': [color],
                    'divider_highlight_group': 'kubernetes:divider'
                })

        return segments

    def __init__(self):
        self.pl = None
        self.show_kube_logo = None
        self.show_cluster = None
        self.show_namespace = None
        self.show_default_namespace = None
        self.alerts = []

        self.api_server_check = False
        self.api_server_check_interval = 15
        self.last_api_server_check = 0
        self.api_server_alive = False

    def __call__(self,
                 pl,
                 segment_info,
                 show_kube_logo=True,
                 show_cluster=True,
                 show_namespace=True,
                 show_default_namespace=False,
                 api_server_check=False,
                 api_server_check_interval=15,
                 alerts=[],
                 **kwargs):
        pl.debug('Running powerline-kubernetes')

        kube_config_location = segment_info['environ'].get('KUBECONFIG', '~/.kube/config')

        self.pl = pl
        self.show_kube_logo = show_kube_logo
        self.show_cluster = show_cluster
        self.show_namespace = show_namespace
        self.show_default_namespace = show_default_namespace
        self.api_server_check = api_server_check
        self.api_server_check_interval = api_server_check_interval
        self.alerts = alerts

        try:
            k8s_merger = kube_config.KubeConfigMerger(kube_config_location)
            k8s_loader = kube_config.KubeConfigLoader(config_dict=k8s_merger.config)

            current_context = k8s_loader.current_context
            ctx = current_context['context']
            context = current_context['name']
            try:
                namespace = ctx['namespace']
            except KeyError:
                namespace = 'default'

            if self.api_server_check:
                self._check_api_server(k8s_merger, k8s_loader, pl)

        except Exception as e:
            pl.error(e)
            return

        return self.build_segments(context, namespace)

    def _check_api_server(self, k8s_merger, k8s_loader, pl):
        current_time = time.monotonic()
        if current_time - self.last_api_server_check > self.api_server_check_interval:
            self.last_api_server_check = current_time

            k8s_merger.save_changes()
            client_config = kubernetes_client.Configuration()
            k8s_loader.load_and_set(client_config)

            version_api = kubernetes_client.VersionApi(kubernetes_client.ApiClient(configuration=client_config))
            try:
                pl.debug(version_api.get_code())
            except Exception as e:
                pl.error(e)
                self.api_server_alive = False
                return
            else:
                self.api_server_alive = True
        elif not self.api_server_alive:
            pl.debug('Assuming kube-apiserver is still dead.')


kubernetes = with_docstring(
    KubernetesSegment(), '''Return the current context.

It will show the current context in config.
It requires kubectl and kubernetes-py to be installed.

Divider highlight group used: ``kubernetes:divider``.

Highlight groups used: ``kubernetes_cluster``,
``kubernetes_cluster:alert``, ``kubernetes_namespace``,
and ``kubernetes_namespace:alert``, .
''')
