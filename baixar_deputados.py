"""Baixa os deputados em exercício, com os dados de perfil, e salva em deputados.json."""
import json, time
from concurrent.futures import ThreadPoolExecutor
import requests

BASE = "https://dadosabertos.camara.leg.br/api/v2"
API = BASE + "/deputados"
HEADERS = {"Accept": "application/json"}

def pegar(url, params=None):
    for tentativa in range(4):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=60)
            if r.status_code == 200:
                return r.json()["dados"]
        except requests.RequestException:
            pass
        time.sleep(3 * (tentativa + 1))
    return None

todos, n = [], 1
while True:
    dados = pegar(API, {"ordem": "ASC", "ordenarPor": "nome", "itens": 100, "pagina": n})
    if dados is None:
        raise SystemExit(f"Falha ao baixar a página {n} da lista")
    todos += dados
    if len(dados) < 100:
        break
    n += 1

def perfil(d):
    item = {"id": d["id"], "nome": d["nome"], "siglaPartido": d["siglaPartido"],
            "siglaUf": d["siglaUf"], "urlFoto": d["urlFoto"]}
    det = pegar(f"{API}/{d['id']}")
    if det:
        u = det.get("ultimoStatus") or {}
        nasc = ""
        if det.get("dataNascimento"):
            nasc = "/".join(reversed(det["dataNascimento"].split("-")))
            if det.get("municipioNascimento"):
                nasc += f" em {det['municipioNascimento']}/{det.get('ufNascimento', '')}"
        item.update({"nomeEleitoral": u.get("nomeEleitoral") or d["nome"],
                     "situacao": u.get("situacao"), "email": u.get("email"),
                     "nomeCivil": det.get("nomeCivil"), "escolaridade": det.get("escolaridade"),
                     "nascimento": nasc})
    return item

with ThreadPoolExecutor(max_workers=5) as ex:
    lista = list(ex.map(perfil, todos))

json.dump(lista, open("deputados.json", "w", encoding="utf-8"), ensure_ascii=False)
com_perfil = sum(1 for d in lista if "nomeCivil" in d)
print(f"{len(lista)} deputados salvos, {com_perfil} com perfil completo")

# Logos dos partidos
partidos = {}
for pt in pegar(f"{BASE}/partidos", {"itens": 100, "ordem": "ASC", "ordenarPor": "sigla"}) or []:
    det = pegar(f"{BASE}/partidos/{pt['id']}")
    if det and det.get("urlLogo"):
        partidos[pt["sigla"]] = det["urlLogo"]
json.dump(partidos, open("partidos.json", "w", encoding="utf-8"), ensure_ascii=False)
print(len(partidos), "logos de partidos salvas")

f = requests.get(lista[0]["urlFoto"], timeout=30)
print("foto de exemplo:", f.status_code, f.headers.get("content-type"))
