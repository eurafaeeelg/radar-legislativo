"""Busca projetos recentes da Câmara e gera resumos com o Gemini.
Salva tudo em resumos.json. A chave vem da variável GEMINI_API_KEY (Secret do GitHub)."""
import base64, json, os, sys, time
import requests

CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
GEMINI = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
CHAVE = os.environ.get("GEMINI_API_KEY")
TIPOS = ["PL", "PEC", "PLP", "MPV"]
POR_TIPO = 8          # quantos projetos recentes olhar por tipo
MAX_NOVOS = 12        # limite de resumos novos por execução (protege a cota grátis)
ARQUIVO = "resumos.json"

PROMPT = """Você analisa projetos de lei brasileiros para o público geral.
Leia o projeto e responda SOMENTE em JSON, em português simples, com este formato:
{"resumo": "2 a 3 frases dizendo o que o projeto faz, sem jargão",
 "mudancas": ["até 4 itens: o que muda na prática para as pessoas"],
 "a_favor": ["até 3 argumentos que os defensores costumam usar"],
 "contra": ["até 3 argumentos que os críticos costumam usar"]}
Regras: seja neutro, não diga como alguém deveria votar, não invente nada que não esteja no texto
e use só o que o documento realmente contém."""

def get(url, **kw):
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=60, **kw)
    r.raise_for_status()
    return r

def chamar_gemini(partes):
    corpo = {"contents": [{"parts": partes}],
             "generationConfig": {"responseMimeType": "application/json"}}
    for tentativa in range(4):
        r = requests.post(GEMINI, json=corpo, timeout=180,
                          headers={"x-goog-api-key": CHAVE, "Content-Type": "application/json"})
        if r.status_code in (429, 503):
            time.sleep(20 * (tentativa + 1))
            continue
        r.raise_for_status()
        texto = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(texto)
    raise RuntimeError("Gemini indisponível ou limite atingido")

def resumir(prop):
    det = get(f"{CAMARA}/proposicoes/{prop['id']}").json()["dados"]
    partes = [{"text": PROMPT}]
    url = det.get("urlInteiroTeor")
    fonte = "ementa"
    if url:
        try:
            arq = requests.get(url, timeout=90)
            if arq.ok and arq.content[:4] == b"%PDF" and len(arq.content) < 15_000_000:
                partes.append({"inline_data": {"mime_type": "application/pdf",
                                               "data": base64.b64encode(arq.content).decode()}})
                fonte = "texto integral"
        except requests.RequestException:
            pass
    if fonte == "ementa":
        partes.append({"text": f"Ementa do projeto: {prop.get('ementa', '')}"})
    out = chamar_gemini(partes)
    out["fonte"] = fonte
    return out

def main():
    if not CHAVE:
        sys.exit("Defina GEMINI_API_KEY nos Secrets do GitHub.")
    try:
        dados = json.load(open(ARQUIVO, encoding="utf-8"))
    except FileNotFoundError:
        dados = {}
    novos = 0
    for tipo in TIPOS:
        lista = get(f"{CAMARA}/proposicoes?siglaTipo={tipo}&ordem=DESC&ordenarPor=id&itens={POR_TIPO}").json()["dados"]
        for p in lista:
            if str(p["id"]) in dados or novos >= MAX_NOVOS:
                continue
            try:
                dados[str(p["id"])] = resumir(p)
                novos += 1
                print("ok", tipo, p["id"])
            except Exception as e:
                print("falhou", p["id"], e)
            time.sleep(8)  # respeita o limite por minuto do plano grátis
    json.dump(dados, open(ARQUIVO, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{novos} resumos novos, {len(dados)} no total")

main()
