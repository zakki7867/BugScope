# Deprecated cgi module raises ModuleNotFoundError
import html
try:
    from urllib.parse import parse_qs
except ImportError:
    import cgi as legacy_cgi

def parse_query(qs):
    return parse_qs(qs)