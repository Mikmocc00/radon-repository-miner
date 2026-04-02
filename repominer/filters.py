import re


def is_ansible_file(path: str) -> bool:
    """
    Check whether the path is an Ansible file
    :param path: a path
    :return: True if the path links to an Ansible file. False, otherwise
    """
    return path \
        and ('test/' not in path) \
        and any(w in path for w in ['playbooks/', 'meta/', 'tasks/', 'handlers/', 'roles/']) and path.endswith('.yml')


def is_tosca_file(path: str, content: str = None) -> bool:
    """
    Check whether the path is a TOSCA file
    :param path: a path
    :param content: eventually the source code
    :return: True if the path links to a TOSCA file. False, otherwise
    """
    if content:
        return re.match(r'^tosca_definitions_version\s*:.+', content) is not None

    return path and ('test' not in path) and any(path.endswith(ext) for ext in ['.tosca', '.tosca.yaml', '.tosca.yml'])


def is_terraform_file(path: str, content: str = None) -> bool:
    """
    Check whether the path is a Terraform file
    """
    return path and path.endswith(".tf")


def is_kubernetes_file(path: str, content: str = None) -> bool:
    """
    Check whether the path is a Kubernetes file
    """
    # Controlla l'estensione e ignora le cartelle di test
    if not path or 'test/' in path or not (path.endswith('.yaml') or path.endswith('.yml')):
        return False

    if content:
        has_api = re.search(r'^apiVersion\s*:.+', content, re.MULTILINE) is not None
        has_kind = re.search(r'^kind\s*:.+', content, re.MULTILINE) is not None
        return has_api and has_kind

    return True


def is_docker_file(path: str, content: str = None) -> bool:
    """
    Check whether the path is a Docker file
    """
    # Ignoriamo i percorsi vuoti o le cartelle di test
    if not path or 'test/' in path.lower():
        return False

    # Estraiamo solo il nome del file dal percorso completo
    filename = path.split('/')[-1].lower()

    # Riconosce sia il classico "Dockerfile" sia estensioni come "app.dockerfile"
    return filename == 'dockerfile' or filename.endswith('.dockerfile')