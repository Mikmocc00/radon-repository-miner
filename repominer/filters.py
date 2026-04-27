import re


def is_ansible_file(path: str) -> bool:
    return path \
        and ('test/' not in path) \
        and any(w in path for w in ['playbooks/', 'meta/', 'tasks/', 'handlers/', 'roles/']) and path.endswith('.yml')


def is_tosca_file(path: str, content: str = None) -> bool:

    if content:
        return re.match(r'^tosca_definitions_version\s*:.+', content) is not None

    return path and ('test' not in path) and any(path.endswith(ext) for ext in ['.tosca', '.tosca.yaml', '.tosca.yml'])


def is_terraform_file(path: str, content: str = None) -> bool:
   
    return path and path.endswith(".tf")


def is_kubernetes_file(path: str, content: str = None) -> bool:
    
    if not path or 'test/' in path or not (path.endswith('.yaml') or path.endswith('.yml')):
        return False

    if content:
        has_api = re.search(r'^apiVersion\s*:.+', content, re.MULTILINE) is not None
        has_kind = re.search(r'^kind\s*:.+', content, re.MULTILINE) is not None
        return has_api and has_kind

    return True


def is_docker_file(path: str, content: str = None) -> bool:
  
    if not path or 'test/' in path.lower():
        return False

  
    filename = path.split('/')[-1].lower()

    return filename == 'dockerfile' or filename.endswith('.dockerfile')
