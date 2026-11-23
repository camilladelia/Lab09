from database.parco_DAO import ParcoDAO
from database.escursione_DAO import EscursioneDAO
from database.punto_interesse_DAO import PuntoInteresseDAO

class Model:
    def __init__(self):
        self.escursioni_map = {} # Mappa ID escursione -> oggetti Escursione
        self.punti_interesse_map = {} # Mappa ID punto di interesse -> oggetti PuntoInteresse

        self._pacchetto_ottimo = []
        self._valore_ottimo: int = -1
        self._costo = 0

        # TODO: Aggiungere eventuali altri attributi
        self._escursioni_parco = []
        self._max_giorni = None
        self._max_budget = None

        # Caricamento
        self.load_escursioni()
        self.load_punti_interesse()
        self.load_relazioni()

    @staticmethod
    def load_parchi():
        """ Restituisce tutti i parchi disponibili """
        return ParcoDAO.get_parchi()

    def load_escursioni(self):
        """ Carica tutte le escursioni in un dizionario [id, Escursione]"""
        self.escursioni_map = EscursioneDAO.get_escursioni()

    def load_punti_interesse(self):
        """ Carica tutti i punti di interesse in un dizionario [id, PuntoInteresse]"""
        self.punti_interesse_map = PuntoInteresseDAO.get_punti_interesse()

    def load_relazioni(self):
        """
            Interroga il database per ottenere tutte le relazioni fra escursioni e punti di interesse e salvarle nelle strutture dati
            Collega escursione <-> punti di interesse.
            --> Ogni Escursione ha un set di PuntoInteresse.
            --> Ogni PuntoInteresse ha un set di Escursioni.
        """
        # 1. Chiediamo al DAO tutte le coppie (id_escursione, id_punto_interesse)
        relazioni = EscursioneDAO.get_escursioni_punti_interesse()

        # Controllo di sicurezza: se la query fallisce, interrompiamo
        if relazioni is None or self.escursioni_map is None or self.punti_interesse_map is None:
            return

        # 2. Scorriamo ogni coppia restituita dal database
        for relazione in relazioni:
            id_e = relazione["id_escursione"]
            id_p = relazione["id_punto_interesse"]

            # 3. Recuperiamo i veri oggetti Python dalle due mappe usando gli ID
            if id_e in self.escursioni_map and id_p in self.punti_interesse_map:
                escursione = self.escursioni_map[id_e]
                punto = self.punti_interesse_map[id_p]

                # 4. Creiamo il doppio collegamento nei rispettivi set (ORM N:N)
                escursione.punti_interesse.add(punto)
                punto.escursioni.add(escursione)


    def genera_pacchetto(self, id_parco: str, max_giorni: int = None, max_budget: float = None):
        """
        Calcola il pacchetto di escursioni ottimale per un parco rispettando i vincoli di durata, budget e punti di interesse unici.
        :param id_parco: id del parco
        :param max_giorni: numero massimo di giorni (può essere None --> nessun limite)
        :param max_budget: costo massimo del pacchetto (può essere None --> nessun limite)

        :return: self._pacchetto_ottimo (una lista di oggetti Escursione)
        :return: self._costo (il costo del pacchetto)
        :return: self._valore_ottimo (il voto complessivo dei visitatori per il pacchetto)
        """
        self._pacchetto_ottimo = []
        self._costo = 0
        self._valore_ottimo = -1

        # TODO
        # 1. Filtriamo solo le escursioni del parco selezionato dall'utente
        self._escursioni_parco = []
        for escursione in self.escursioni_map.values():
            if escursione.id_parco == id_parco:
                self._escursioni_parco.append(escursione)

        # 2. Salviamo i vincoli negli attributi di classe per usarli nella ricorsione
        self._max_giorni = max_giorni
        self._max_budget = max_budget

        # 3. Avviamo l'algoritmo ricorsivo partendo dall'indice 0 e tutto vuoto/a zero
        self._ricorsione(
            start_index=0,
            pacchetto_parziale=[],
            durata_corrente=0,
            costo_corrente=0.0,
            valore_corrente=0,
            punti_usati=set()
        )

        return self._pacchetto_ottimo, self._costo, self._valore_ottimo

    def _ricorsione(self, start_index: int, pacchetto_parziale: list, durata_corrente: int, costo_corrente: float, valore_corrente: int, punti_usati: set):
        """ Algoritmo di ricorsione che deve trovare il pacchetto che massimizza il voto complessivo dei visitatori"""

        # TODO: è possibile cambiare i parametri formali della funzione se ritenuto opportuno
        # --- A. CONTROLLO DEL RECORD (eseguito sempre) ---
        # Qualunque pacchetto valido può essere quello ottimo, quindi controlliamo subito
        if valore_corrente > self._valore_ottimo:
            self._valore_ottimo = valore_corrente
            self._costo = costo_corrente
            # Usiamo .copy() per salvare una fotografia indipendente della lista attuale
            self._pacchetto_ottimo = pacchetto_parziale.copy()

        # --- B. CONDIZIONE DI TERMINAZIONE ---
        # Non serve un 'if' esplicito: quando start_index raggiunge la fine della lista,
        # il ciclo 'for' qui sotto non esegue alcun giro e la ricorsione si ferma da sola.

        # --- CICLO SULLE ESCURSIONI RIMANENTI ---
        for i in range(start_index, len(self._escursioni_parco)):
            escursione = self._escursioni_parco[i]

            # --- C. FILTRI (VERIFICA DEI VINCOLI) ---
            # Vincolo 1: Durata massima (controlliamo solo se l'utente ha inserito un limite)
            if self._max_giorni is not None and durata_corrente + escursione.durata_giorni > self._max_giorni:
                continue

            # Vincolo 2: Budget massimo (controlliamo solo se l'utente ha inserito un limite)
            if self._max_budget is not None and costo_corrente + escursione.costo > self._max_budget:
                continue

            # Vincolo 3: Nessun punto di interesse duplicato
            # .intersection() trova gli elementi in comune tra due set: se ce n'è almeno uno, scartiamo!
            if len(punti_usati.intersection(escursione.punti_interesse)) > 0:
                continue

            # --- D. COSTRUZIONE DELLA SOLUZIONE PARZIALE ---
            # Calcoliamo il punteggio portato da questa escursione sommando i voti dei suoi punti
            voto_escursione = sum(p.voto_visitatori for p in escursione.punti_interesse)

            pacchetto_parziale.append(escursione)
            punti_usati.update(escursione.punti_interesse)

            # --- E. PASSO RICORSIVO ---
            # Passiamo i + 1 così non riproveremo mai la stessa escursione né combinazioni già viste
            self._ricorsione(
                start_index=i + 1,
                pacchetto_parziale=pacchetto_parziale,
                durata_corrente=durata_corrente + escursione.durata_giorni,
                costo_corrente=costo_corrente + escursione.costo,
                valore_corrente=valore_corrente + voto_escursione,
                punti_usati=punti_usati
            )

            # --- F. BACKTRACKING ---
            # Togliamo l'escursione e i suoi punti di interesse per provare altre strade al giro successivo
            pacchetto_parziale.pop()
            punti_usati.difference_update(escursione.punti_interesse)
