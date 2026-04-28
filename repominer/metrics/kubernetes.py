from .base import BaseMetricsExtractor
from repominer.filters import is_kubernetes_file
from radon_kubernetes_metrics.import_metrics import general_metrics, manifest_metrics
import pandas as pd
from pydriller import Repository, ModificationType
from radon_kubernetes_metrics.utils import ParsedManifest

METRICS_TO_COMPUTE = (
    'config_entropy',
    'avg_fields_per_resource',
    'num_labels',
    'num_total_fields',
    'nested_object_ratio',
    'manifest_structural_complexity',
    'num_resources',
    'num_configmaps',
    'num_persistent_volumes',
    'num_tolerations',
    'num_affinity_rules',
    'num_node_selectors',
    'num_ports',
    'num_resource_limits'
)

class KubernetesMetricsExtractor(BaseMetricsExtractor):

    def get_product_metrics(self, script: str) -> dict:
        if not script:
            return {}

        results = {}

        all_metrics = {**general_metrics, **manifest_metrics}

        try:
            manifest_wrapper = ParsedManifest(script)
        except Exception:
            manifest_wrapper = None

        for metric_name in METRICS_TO_COMPUTE:
            metric_class = all_metrics.get(metric_name)

            if not metric_class:
                continue

            try:
                if metric_name in manifest_metrics and manifest_wrapper is not None:
                    results[metric_name] = metric_class(manifest_wrapper).count()

                else:
                    results[metric_name] = metric_class(script).count()

            except Exception:
                results[metric_name] = 0

        return results

    def extract(self, labeled_files, product=True, process=True, delta=False):
        labeled_set = {(f.filepath, f.commit) for f in labeled_files}
        dataset_rows = []
        product_cache = {}

        repo = Repository(self.path_to_repo, order='date-order')

        total_commits = len(self.commits_at)
        processed_commits = 0

        for commit in repo.traverse_commits():

            for m_file in commit.modified_files:
                path = m_file.new_path or m_file.old_path

                if m_file.change_type == ModificationType.DELETE:
                    product_cache.pop(path, None)
                elif is_kubernetes_file(path, m_file.source_code):
                    product_cache[path] = self.get_product_metrics(m_file.source_code)

            if commit.hash not in self.commits_at:
                continue

            processed_commits += 1
            if total_commits > 0:
                percentuale = (processed_commits / total_commits) * 100
                print(f"[ESTRAZIONE] Progresso: {processed_commits}/{total_commits} ({percentuale:.1f}%) - Commit {commit.hash[:8]}", flush=True)

            process_metrics = {}
            if process:
                try:
                    curr_idx = self.commits_at.index(commit.hash)
                    from_hash = self.commits_at[0] if curr_idx == 0 else self.commits_at[curr_idx - 1]
                    process_metrics = self.get_process_metrics(from_hash, commit.hash)
                except ValueError:
                    continue

            for filepath, p_metrics in product_cache.items():
                label = 1 if (filepath, commit.hash) in labeled_set else 0

                row = {
                    'filepath': filepath,
                    'commit': commit.hash,
                    'committed_at': str(commit.committer_date),
                    'failure_prone': label,
                    **p_metrics
                }

                if process:
                    for m_name, m_data in process_metrics.items():
                        clean_name = m_name.replace('dict_', '')
                        if isinstance(m_data, dict):
                            row[clean_name] = m_data.get(filepath, 0)
                        else:
                            row[clean_name] = m_data

                dataset_rows.append(row)

        self.dataset = pd.DataFrame(dataset_rows)

    def ignore_file(self, path_to_file: str, content: str = None):
        return not is_kubernetes_file(path_to_file, content)