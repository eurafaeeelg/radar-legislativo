"""Baixa a lista de deputados em exercício e salva em deputados.json."""
import json, time
import requests

API = "https://dadosabertos.camara.leg.br/api/v2/deputados"

def pagina(n):
    for tentativa in range(4):
        r = requests.get(API, params={"ordem": "ASC", "ordenarPor": "nome", "itens": 100, "pagina": n},
                         headers={"Accept": "application/json"}, timeout=60)
        if r.status_code == 200:
            return r.json()["dados"]
        time.sleep(5 * (tentativa + 1))
    r.raise_for_status()

todos, n = [], 1
while True:
    dados = pagina(n)
    todos += dados
    if len(dados) < 100:
        break
    n += 1

lista = [{"id": d["id"], "nome": d["nome"], "siglaPartido": d["siglaPartido"],
          "siglaUf": d["siglaUf"], "urlFoto": d["urlFoto"]} for d in todos]
json.dump(lista, open("deputados.json", "w", encoding="utf-8"), ensure_ascii=False)
print(len(lista), "deputados salvos")

# Diagnóstico: confere se a foto do primeiro deputado abre
if lista:
    f = requests.get(lista[0]["urlFoto"], timeout=30)
    print("foto de exemplo:", f.status_code, f.headers.get("content-type"))
