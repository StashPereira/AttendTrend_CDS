import json
import sys
from .services.documents import extract, parse

if __name__ == "__main__":
    # Extraction runs in a disposable subprocess with a memory ceiling on Linux.
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
    except ImportError:
        pass
    print(json.dumps(parse(extract(sys.argv[1], sys.argv[2]), sys.argv[2])))
