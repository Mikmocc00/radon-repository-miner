from .base import BaseMetricsExtractor
from repominer.filters import is_kubernetes_file
from radon_kubernetes_metrics.import_metrics import general_metrics, manifest_metrics
import pandas as pd
from pydriller import Repository, ModificationType
from radon_kubernetes_metrics.utils import ParsedManifest

METRICS_TO_COMPUTE = tuple(manifest_metrics.keys()) + tuple(general_metrics.keys())

class KubernetesMetricsExtractor(BaseMetricsExtractor):

    def get_product_metrics(self, script: str) -> dict:
        if not script:
            return {}

        results = {}

        # 1. Eseguiamo le metriche generali passando la stringa grezza
        for name, metric_class in general_metrics.items():
            try:
                results[name] = metric_class(script).count()
            except Exception:
                results[name] = 0

        # 2. Creiamo l'oggetto ottimizzato per YAML UNA SOLA VOLTA
        try:
            manifest_wrapper = ParsedManifest(script)
        except Exception:
            # Se il parsing fallisce pesantemente, saltiamo le metriche manifest
            return results

            # 3. Eseguiamo le metriche manifest passando l'oggetto cache
        for name, metric_class in manifest_metrics.items():
            try:
                results[name] = metric_class(manifest_wrapper).count()
            except Exception:
                results[name] = 0

        return results

    def extract(self, labeled_files, product=True, process=True):
        labeled_set = {(f.filepath, f.commit) for f in labeled_files}
        dataset_rows = []
        product_cache = {}

        # Iteriamo solo sui commit che sono RELEASES
        # Usiamo traverse_commits() che è più efficiente con only_releases=True
        repo = Repository(self.path_to_repo, only_releases=True, order='date-order')

        for commit in repo.traverse_commits():

            # 1. AGGIORNAMENTO CACHE (Basato sui file modificati nel commit della release)
            for m_file in commit.modified_files:
                path = m_file.new_path or m_file.old_path

                if m_file.change_type == ModificationType.DELETE:
                    product_cache.pop(path, None)

                # Usiamo il filtro is_kubernetes_file che hai postato
                elif self.is_kubernetes_file(path, m_file.source_code):
                    product_cache[path] = self.get_product_metrics(m_file.source_code)

            # 2. METRICHE DI PROCESSO
            process_metrics = {}
            if process:
                try:
                    curr_idx = self.commits_at.index(commit.hash)
                    # Intervallo: dalla release precedente (o inizio) a questa
                    from_hash = self.commits_at[0] if curr_idx == 0 else self.commits_at[curr_idx - 1]
                    process_metrics = self.get_process_metrics(from_hash, commit.hash)
                except ValueError:
                    # Se per qualche motivo il commit non è in commits_at
                    continue

            # 3. CREAZIONE RIGHE DATASET
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
                    # Mappatura sicura delle metriche di processo
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