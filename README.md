# Automercatorum Downloader di dispense

App desktop per macOS che scarica in automatico tutte le **dispense PDF** dalle tue materie sul portale [Universitas Mercatorum](https://lms.mercatorum.multiversity.click/).

Login una volta, seleziona le materie, scarica tutto. Niente browser, niente scraping.

<img width="1028" height="788" alt="Screenshot 2026-05-18 at 2 55 08 PM" src="https://github.com/user-attachments/assets/580ae68d-2ddb-432e-89aa-d79cde8569ff" />
<img width="1072" height="832" alt="Screenshot 2026-05-18 at 12 39 42 PM" src="https://github.com/user-attachments/assets/59ab7cda-03ed-4dbc-b276-0e18cbc86eb3" />
<img width="1072" height="832" alt="Screenshot 2026-05-18 at 12 38 25 PM" src="https://github.com/user-attachments/assets/e6e6ab0d-ebd3-4ade-acf2-2c9f090599ec" />

## Avvio

```bash
git clone https://github.com/<tu>/Automercatorum-Downloader-di-dispense.git
cd Automercatorum-Downloader-di-dispense

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python app.py
```

Si apre una finestra: inserisci username e password Mercatorum (spunta *Salva credenziali* per non rifarlo), seleziona le materie, clicca **Scarica selezionate**. I PDF arrivano in `downloads/<Nome materia>/`.

## CLI (opzionale)

```bash
python download.py --list          # mostra le tue materie
python download.py <CODICE>        # scarica una materia
python download.py --all           # scaricale tutte
```

## Note

- Richiede Python 3.11+
- Credenziali salvate in chiaro in `.auth/creds.json` (permission `0600`, gitignored)
- Solo per uso personale di studio. Rispetta i termini del tuo ateneo.

## Licenza

[MIT](LICENSE)
