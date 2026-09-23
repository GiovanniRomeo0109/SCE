"""
services/tappe_definizioni.py — Le 12 tappe del PSC (sequenza logica della metodologia SafetyDocs)

Ogni tappa produce SEZIONI STRUTTURATE:
  - tipo "testo":   paragrafo modificabile
  - tipo "tabella": colonne fisse, righe modificabili una per una
più due elenchi: "da_verificare" (dati mancanti o incerti) e "domande_sopralluogo".

Le tappe seguono le 12 domande (COSA → DOVE → CHI → ... → È applicabile?).
Il documento finale (blocco 6) le riorganizzerà nei 12 capitoli dell'Allegato XV.
"""
import json

T = "testo"
TAB = "tabella"
RESP = "Responsabile / condizione di attuazione"

TAPPE = [
    {
        "numero": 1, "codice": "cosa", "titolo": "COSA devo costruire?",
        "obiettivo": (
            "Descrivi l'opera: cosa va costruito, demolito o modificato, tipologia di intervento, "
            "dimensioni, altezze, materiali e tecnologie. Analizza il progetto dal punto di vista "
            "della sicurezza (metodologia, punti 1, 2 e 4): quali scelte progettuali possono "
            "eliminare o ridurre i rischi già in fase di progetto."),
        "sezioni": [
            {"id": "descrizione", "titolo": "Descrizione dell'opera e dell'intervento", "tipo": T},
            {"id": "dati_opera", "titolo": "Dati principali dell'opera", "tipo": TAB,
             "colonne": ["Dato", "Valore", "Fonte (documento e pagina)"]},
            {"id": "analisi_progetto", "titolo": "Analisi del progetto ai fini della sicurezza", "tipo": T},
            {"id": "scelte_progettuali", "titolo": "Scelte progettuali e organizzative per ridurre i rischi", "tipo": TAB,
             "colonne": ["Aspetto del progetto", "Rischio collegato", "Scelta proposta al progettista / committente"]},
        ],
    },
    {
        "numero": 2, "codice": "dove", "titolo": "DOVE lo devo costruire?",
        "obiettivo": (
            "Analizza l'area di cantiere e il contesto (metodologia, punti 3 e 10; Allegato XV "
            "punto 2.2.1): accessi, viabilità, edifici confinanti, sottoservizi, linee aeree, "
            "alberature, vincoli, rischi ambientali (allagamento, terreno, ecc.), rischi che "
            "l'ambiente trasmette al cantiere e che il cantiere trasmette all'esterno."),
        "sezioni": [
            {"id": "inquadramento", "titolo": "Inquadramento dell'area", "tipo": T},
            {"id": "caratteristiche_area", "titolo": "Caratteristiche dell'area e del contesto", "tipo": TAB,
             "colonne": ["Aspetto", "Situazione rilevata", "Rischio o vincolo", "Fonte"]},
            {"id": "rischi_esterni", "titolo": "Rischi trasmessi dall'esterno al cantiere e dal cantiere all'esterno", "tipo": TAB,
             "colonne": ["Direzione", "Pericolo", "Rischio", "Misura"]},
        ],
    },
    {
        "numero": 3, "codice": "chi", "titolo": "CHI lavorerà?",
        "obiettivo": (
            "Individua i soggetti (committente, responsabile dei lavori, progettista, direttore "
            "lavori, CSP, CSE) e le imprese/lavoratori autonomi previsti. Le imprese non ancora "
            "note vanno indicate per categoria, es. 'Impresa impianti elettrici — da individuare'."),
        "sezioni": [
            {"id": "soggetti", "titolo": "Soggetti con compiti di sicurezza", "tipo": TAB,
             "colonne": ["Ruolo", "Nominativo", "Recapiti / riferimenti"]},
            {"id": "imprese", "titolo": "Imprese e lavoratori autonomi", "tipo": TAB,
             "colonne": ["Impresa / lavoratore autonomo", "Specializzazione", "Stato (individuata / da individuare)", "Note"]},
            {"id": "note_soggetti", "titolo": "Note", "tipo": T},
        ],
    },
    {
        "numero": 4, "codice": "cosa_ciascuno", "titolo": "COSA farà ciascuno?",
        "obiettivo": (
            "Individua tutte le lavorazioni e scomponile in fasi e sottofasi (metodologia, punti 5, "
            "6 e 7), associando a ciascuna l'impresa esecutrice individuata alla tappa 3. Riporta "
            "le quantità indicative dal computo quando disponibili."),
        "max_tokens": 12000,
        "sezioni": [
            {"id": "lavorazioni", "titolo": "Lavorazioni, fasi e sottofasi", "tipo": TAB,
             "colonne": ["Cod.", "Lavorazione", "Fase / sottofase", "Impresa esecutrice", "Quantità indicativa"]},
            {"id": "note_lavorazioni", "titolo": "Note sulle lavorazioni", "tipo": T},
        ],
    },
    {
        "numero": 5, "codice": "quando", "titolo": "QUANDO lo farà?",
        "obiettivo": (
            "Proponi il cronoprogramma in SETTIMANE (metodologia, punto 15): durata delle fasi e "
            "sottofasi, sequenza, lavorazioni contemporanee. Se nei documenti c'è già un "
            "cronoprogramma, usalo; altrimenti stimalo da lavorazioni e quantità. La settimana 1 "
            "coincide con la data di inizio lavori indicata dal CSP (se assente: DA VERIFICARE)."),
        "sezioni": [
            {"id": "impostazione", "titolo": "Impostazione del cronoprogramma", "tipo": T},
            {"id": "cronoprogramma", "titolo": "Cronoprogramma (settimane)", "tipo": TAB,
             "colonne": ["Cod.", "Fase / lavorazione", "Impresa", "Settimana inizio", "Durata (settimane)", "Settimana fine", "Contemporanea a"]},
        ],
    },
    {
        "numero": 6, "codice": "rischi", "titolo": "COSA può andare storto?",
        "obiettivo": (
            "Analizza i rischi dell'area, delle singole lavorazioni e i rischi particolari "
            "dell'Allegato XI (metodologia, punti 10, 11, 17, 18 e 19). Per ogni rischio arriva a una "
            "misura concreta nella forma PERICOLO → RISCHIO → MISURA PREVENTIVA → MISURA PROTETTIVA → "
            "RESPONSABILE/CONDIZIONE. Privilegia l'eliminazione del rischio e le protezioni "
            "collettive; i DPI solo quando necessari."),
        "max_tokens": 14000,
        "sezioni": [
            {"id": "rischi_area", "titolo": "Rischi dell'area di cantiere", "tipo": TAB,
             "colonne": ["Pericolo", "Rischio", "Misura preventiva", "Misura protettiva", RESP]},
            {"id": "rischi_lavorazioni", "titolo": "Rischi delle lavorazioni", "tipo": TAB,
             "colonne": ["Lavorazione", "Pericolo", "Rischio", "Misura preventiva", "Misura protettiva", RESP]},
            {"id": "rischi_particolari", "titolo": "Rischi particolari (Allegato XI) e lavorazioni particolari", "tipo": TAB,
             "colonne": ["Rischio particolare", "Presente?", "Lavorazioni interessate", "Misure"]},
            {"id": "amianto", "titolo": "Amianto", "tipo": T},
        ],
    },
    {
        "numero": 7, "codice": "interferenze", "titolo": "QUALI interferenze possono verificarsi?",
        "obiettivo": (
            "Dal cronoprogramma (tappa 5) e dalle lavorazioni (tappa 4) individua le interferenze "
            "(metodologia, punto 8): lavorazioni contemporanee o nella stessa area, uso comune di "
            "attrezzature, chi può accedere alla zona, quali rischi produce una lavorazione sull'altra."),
        "sezioni": [
            {"id": "interferenze", "titolo": "Interferenze individuate", "tipo": TAB,
             "colonne": ["Lavorazione A", "Lavorazione B", "Periodo (settimane)", "Area", "Tipo di interferenza", "Rischio indotto"]},
            {"id": "note_interferenze", "titolo": "Note", "tipo": T},
        ],
    },
    {
        "numero": 8, "codice": "eliminare", "titolo": "COME posso eliminarle o ridurle?",
        "obiettivo": (
            "Per ogni interferenza della tappa 7 proponi la soluzione (metodologia, punto 9): prima "
            "eliminarla (sfasamento temporale o spaziale), poi ridurla con procedure, protezioni "
            "collettive, segregazioni; indica chi attua la misura e come si verifica."),
        "sezioni": [
            {"id": "misure_interferenze", "titolo": "Prescrizioni per le interferenze", "tipo": TAB,
             "colonne": ["Interferenza", "Soluzione (sfasamento temporale / spaziale / procedura / protezione)", "Misura prescritta", RESP, "Verifica"]},
            {"id": "principi", "titolo": "Criteri generali adottati", "tipo": T},
        ],
    },
    {
        "numero": 9, "codice": "organizzazione", "titolo": "COME organizzo fisicamente il cantiere?",
        "obiettivo": (
            "Progetta l'organizzazione del cantiere (metodologia, punti 12, 13 e 14; Allegato XV "
            "punto 2.2.2): recinzione, accessi e segnaletica, viabilità, servizi igienico-assistenziali, "
            "depositi, aree di lavorazione, apparecchi di sollevamento, impianti, rifiuti, e le "
            "emergenze (primo soccorso, antincendio, evacuazione, chiamata soccorsi). I presidi "
            "esterni (pronto soccorso, vigili del fuoco) vanno indicati come DA VERIFICARE se non "
            "presenti nel fascicolo. La planimetria grafica sarà disegnata a parte."),
        "sezioni": [
            {"id": "layout", "titolo": "Descrizione dell'organizzazione del cantiere", "tipo": T},
            {"id": "elementi_cantiere", "titolo": "Elementi dell'organizzazione di cantiere", "tipo": TAB,
             "colonne": ["Elemento", "Soluzione prevista", "Posizione nel cantiere", "Note"]},
            {"id": "emergenze", "titolo": "Gestione delle emergenze", "tipo": T},
            {"id": "presidi", "titolo": "Presidi e numeri di emergenza", "tipo": TAB,
             "colonne": ["Presidio", "Riferimento / numero", "Distanza o percorso indicativo"]},
        ],
    },
    {
        "numero": 10, "codice": "coordinamento", "titolo": "COME organizzo il coordinamento?",
        "obiettivo": (
            "Stabilisci chi può utilizzare cosa e l'organizzazione di cooperazione, coordinamento e "
            "reciproca informazione (metodologia, punti 20 e 21; Allegato XV punti 2.1.2 lett. g-h)."),
        "sezioni": [
            {"id": "uso_comune", "titolo": "Uso comune di apprestamenti, attrezzature, infrastrutture e servizi", "tipo": TAB,
             "colonne": ["Apprestamento / attrezzatura", "Chi installa", "Chi mette a disposizione", "Chi utilizza", "Chi verifica", "Chi manutiene"]},
            {"id": "attivita_coordinamento", "titolo": "Attività di coordinamento", "tipo": TAB,
             "colonne": ["Momento", "Attività", "Partecipanti", "Documentazione prodotta"]},
            {"id": "cooperazione", "titolo": "Cooperazione e reciproca informazione", "tipo": T},
        ],
    },
    {
        "numero": 11, "codice": "costi", "titolo": "QUANTO costano le misure di sicurezza?",
        "obiettivo": (
            "Elenca le misure che generano costi della sicurezza del PSC applicando la regola delle "
            "tre domande e le 7 categorie dell'Allegato XV punto 4.1.1 (sezione COSTI della "
            "metodologia). NON indicare prezzi: verranno applicati dagli elenchi prezzi in un passo "
            "successivo. Indica unità di misura e quantità stimate. Elenca separatamente le voci "
            "che restano costi ordinari dell'impresa, con il motivo."),
        "max_tokens": 12000,
        "sezioni": [
            {"id": "costi_psc", "titolo": "Misure che rientrano nei costi della sicurezza del PSC", "tipo": TAB,
             "colonne": ["Categoria 4.1.1 (a-g)", "Misura", "Motivazione (tre domande)", "U.M.", "Quantità", "Note"]},
            {"id": "costi_ordinari", "titolo": "Voci escluse: costi ordinari delle imprese", "tipo": TAB,
             "colonne": ["Voce", "Motivo dell'esclusione"]},
            {"id": "criteri_stima", "titolo": "Criteri di stima", "tipo": T},
        ],
    },
    {
        "numero": 12, "codice": "applicabile", "titolo": "IL PSC è realmente applicabile?",
        "obiettivo": (
            "Esegui il controllo di coerenza (metodologia, punto 24): Progetto ↔ PSC, PSC ↔ "
            "planimetria/organizzazione, PSC ↔ cronoprogramma, PSC ↔ costi, PSC ↔ POS, PSC ↔ realtà. "
            "Per ogni verifica dai un esito (OK / Da correggere / DA VERIFICARE) e indica la tappa da "
            "rivedere. Concludi con un giudizio di concreta fattibilità."),
        "sezioni": [
            {"id": "coerenza", "titolo": "Controllo di coerenza", "tipo": TAB,
             "colonne": ["Verifica", "Esito", "Osservazioni", "Tappa da rivedere"]},
            {"id": "fattibilita", "titolo": "Giudizio di concreta fattibilità", "tipo": T},
        ],
    },
]

TAPPE_PER_NUMERO = {t["numero"]: t for t in TAPPE}
NUMERO_TAPPE = len(TAPPE)


def definizione(numero: int) -> dict:
    return TAPPE_PER_NUMERO[numero]


def scheletro(numero: int) -> dict:
    """Struttura JSON che l'AI deve restituire per la tappa."""
    t = definizione(numero)
    sezioni = []
    for s in t["sezioni"]:
        if s["tipo"] == T:
            sezioni.append({"id": s["id"], "titolo": s["titolo"], "tipo": T, "testo": "..."})
        else:
            sezioni.append({"id": s["id"], "titolo": s["titolo"], "tipo": TAB,
                            "colonne": s["colonne"], "righe": [["..." for _ in s["colonne"]]]})
    return {"sezioni": sezioni,
            "da_verificare": [{"campo": "...", "motivo": "..."}],
            "domande_sopralluogo": ["..."]}


def _cella(v) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v).strip()


def normalizza(numero: int, dati) -> dict:
    """
    Porta qualunque risposta (dell'AI o del CSP) sulla struttura fissa della tappa:
    sezioni nell'ordine previsto, colonne invariate, righe della lunghezza giusta.
    """
    t = definizione(numero)
    dati = dati if isinstance(dati, dict) else {}
    ricevute = {s.get("id"): s for s in dati.get("sezioni", []) if isinstance(s, dict)}
    sezioni = []
    for s in t["sezioni"]:
        r = ricevute.get(s["id"], {})
        if s["tipo"] == T:
            testo = r.get("testo", "")
            sezioni.append({"id": s["id"], "titolo": s["titolo"], "tipo": T,
                            "testo": _cella(testo) if not isinstance(testo, str) else testo.strip()})
        else:
            colonne = s["colonne"]
            righe = []
            for riga in r.get("righe", []) or []:
                if isinstance(riga, dict):                  # riga come {colonna: valore}
                    riga = [riga.get(c, "") for c in colonne]
                if not isinstance(riga, list):
                    continue
                riga = [_cella(v) for v in riga][:len(colonne)]
                riga += [""] * (len(colonne) - len(riga))
                if any(c for c in riga):
                    righe.append(riga)
            sezioni.append({"id": s["id"], "titolo": s["titolo"], "tipo": TAB,
                            "colonne": colonne, "righe": righe})

    da_verificare = []
    for d in dati.get("da_verificare", []) or []:
        if isinstance(d, dict) and (d.get("campo") or d.get("motivo")):
            da_verificare.append({"campo": _cella(d.get("campo")), "motivo": _cella(d.get("motivo"))})
        elif isinstance(d, str) and d.strip():
            da_verificare.append({"campo": d.strip(), "motivo": ""})
    domande = [(_cella(q) if not isinstance(q, str) else q.strip())
               for q in dati.get("domande_sopralluogo", []) or []]
    return {"sezioni": sezioni, "da_verificare": da_verificare,
            "domande_sopralluogo": [q for q in domande if q]}


def conta_da_verificare(contenuto: dict) -> int:
    """Occorrenze di 'DA VERIFICARE' nel testo e nelle celle, più l'elenco esplicito."""
    n = 0
    for s in (contenuto or {}).get("sezioni", []):
        if s["tipo"] == T:
            n += s.get("testo", "").upper().count("DA VERIFICARE")
        else:
            n += sum(c.upper().count("DA VERIFICARE") for r in s.get("righe", []) for c in r)
    return n
