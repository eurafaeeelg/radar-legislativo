"""Gera uma apresentação curta de cada deputado com o Gemini, usando só dados oficiais.
Lê deputados.json e salva em deputados_resumos.json. Faz até MAX_NOVOS por execução."""
import json, os, sys, time
import requests

CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
CHAVE = os.environ.get("GEMINI_API_KEY")
MAX_NOVOS = 600   # todos os deputados em uma execução
ARQUIVO = "deputados_resumos.json"

PROMPT = """Você escreve uma apresentação curta de um deputado federal brasileiro para o público geral.
Use SOMENTE os dados abaixo. Escreva 2 frases em português simples e tom neutro: quem é (partido, estado e
formação, se houver) e quais temas aparecem nos projetos que apresentou recentemente.
Regras: não opine, não elogie nem critique, não avalie o mandato, não cite nada que não esteja nos dados
e não diga como votar. Responda SOMENTE em JSON: {"resumo": "..."}

Dados:
"""

def get(url, params=None):
    r = requests.get(url, params=params, headers={"Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    return r.json()["dados"]

def gemini(texto):
    corpo = {"contents": [{"parts": [{"text": texto}]}],
             "generationConfig": {"responseMimeType": "application/json"}}
    for tentativa in range(4):
        r = requests.post(GEMINI, json=corpo, timeout=120,
                          headers={"x-goog-api-key": CHAVE, "Content-Type": "application/json"})
        if r.status_code in (429, 503):
            time.sleep(20 * (tentativa + 1))
            continue
        r.raise_for_status()
        return json.loads(r.json()["candidates"][0]["content"]["parts"][0]["text"])["resumo"]
    raise RuntimeError("limite do Gemini atingido")

def salvar(dados):
    json.dump(dados, open(ARQUIVO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def main():
    if not CHAVE:
        sys.exit("Defina GEMINI_API_KEY nos Secrets do GitHub.")
    deps = json.load(open("deputados.json", encoding="utf-8"))
    try:
        dados = json.load(open(ARQUIVO, encoding="utf-8"))
    except FileNotFoundError:
        dados = {}
    novos = falhas = 0
    for d in deps:
        if str(d["id"]) in dados or novos >= MAX_NOVOS:
            continue
        try:
            props = get(f"{CAMARA}/proposicoes", {"idDeputadoAutor": d["id"], "ordem": "DESC",
                                                    "ordenarPor": "id", "itens": 10})
            ementas = [f"- {p['siglaTipo']} {p['numero']}/{p['ano']}: {(p.get('ementa') or '')[:220]}" for p in props]
            if not ementas:
                dados[str(d["id"])] = None   # sem projetos de autoria: nada a resumir
                continue
            fatos = (f"Nome: {d.get('nomeEleitoral') or d['nome']}\nPartido: {d['siglaPartido']}\nEstado: {d['siglaUf']}\n"
                     f"Escolaridade: {d.get('escolaridade') or 'não informada'}\n"
                     f"Projetos recentes de autoria:\n" + "\n".join(ementas))
            dados[str(d["id"])] = gemini(PROMPT + fatos)
            novos += 1
            falhas = 0
            print("ok", d["nome"])
            if novos % 20 == 0:
                salvar(dados)
        except Exception as e:
            print("falhou", d["nome"], e)
            falhas += 1
            if falhas >= 3:
                print("Limite do Gemini atingido. Parando; o resto fica para a próxima execução.")
                break
        time.sleep(7)
    salvar(dados)
    print(f"{novos} resumos novos, {len(dados)} no total")

main()
