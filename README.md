# Automercatorum Downloader di dispense

App desktop per macOS che scarica in automatico tutte le **dispense PDF** dalle tue materie sul portale [Universitas Mercatorum](https://lms.mercatorum.multiversity.click/).

Login una volta, seleziona le materie, scarica tutto. Niente browser, niente scraping.

<img width="1072" height="832" alt="Screenshot 2026-05-18 at 12 37 40 PM" src="https://github.com/user-attachments/assets/69006768-a106-4097-a4d7-ba55fd9543cd" />
<img width="1072" height="832" alt="Screenshot 2026-05-18 at 12 38 25 PM" src="https://github.com/user-attachments/assets/c8e4c149-0720-4d95-a561-ff92320b81d0" />
<img width="1072" height="832" alt="Screenshot 2026-05-18 at 12 39 42 PM" src="https://github.com/user-attachments/assets/6f0eb29d-4c05-42a1-be1b-09cb2467ad2d" />

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
