import sys
import urllib.request

segundos = sys.argv[1] if len(sys.argv) > 1 else "45"
solicitud = urllib.request.Request(
    f"http://localhost:8000/admin/congelar?segundos={segundos}", method="POST"
)
print(urllib.request.urlopen(solicitud).read().decode())
