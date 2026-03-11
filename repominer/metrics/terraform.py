from .base import BaseMetricsExtractor
from repominer.filters import is_terraform_file
from import_metrics import general_metrics, configuration_metrics

# Metti qui solo le metriche che vuoi davvero calcolare
METRICS_TO_COMPUTE = tuple(configuration_metrics.keys()) + tuple(general_metrics.keys())


class TerraformMetricsExtractor(BaseMetricsExtractor):

    def get_product_metrics(self, script: str) -> dict:
        results = {}

        # Unire tutti i dizionari delle metriche
        all_metrics = {**general_metrics, **configuration_metrics}

        for metric_name in METRICS_TO_COMPUTE:
            metric_class = all_metrics[metric_name]
            try:
                results[metric_name] = metric_class(script).count()
            except Exception:
                results[metric_name] = 0 # fallback se la metrica fallisce

        return results

    def ignore_file(self, path_to_file: str, content: str = None):
        return not is_terraform_file(path_to_file)