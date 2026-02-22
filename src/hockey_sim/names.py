from __future__ import annotations

import random

COACH_FIRST_NAMES: tuple[str, ...] = (
    "Alex",
    "Martin",
    "Chris",
    "Ryan",
    "Mike",
    "Craig",
    "Derek",
    "Pat",
    "Scott",
    "John",
    "Barry",
    "Paul",
    "Todd",
    "Dan",
    "Rick",
    "Andre",
    "Sergei",
    "Jon",
    "Ken",
    "Brent",
    "Claude",
    "Bruce",
    "Lindy",
    "Jacques",
    "Patrick",
    "Luke",
    "Travis",
    "Marco",
    "Pascal",
    "Guy",
    "Dean",
    "Kevin",
    "Jared",
    "Randy",
    "Dave",
)

COACH_LAST_NAMES: tuple[str, ...] = (
    "Sullivan",
    "Cooper",
    "Cassidy",
    "DeBoer",
    "Brindamour",
    "Montgomery",
    "Ruff",
    "Laviolette",
    "Boudreau",
    "Quinn",
    "Woodcroft",
    "Gallant",
    "Berube",
    "Tortorella",
    "Keefe",
    "Maurice",
    "Hynes",
    "Martin",
    "Carbery",
    "Knoblauch",
    "Hakstol",
    "Richardson",
    "MacLean",
    "Muller",
    "Gonchar",
    "Leach",
    "Yeo",
    "Evason",
    "Lemaire",
    "Vigneault",
    "Babcock",
    "Hitchcock",
    "Sutter",
    "Hartley",
    "MacTavish",
)

FIRST_NAMES = sorted(
    {
    "Alex", "Noah", "Liam", "Ethan", "Lucas", "Mason", "Logan", "Aiden", "Owen", "Wyatt",
    "Carter", "Hudson", "Dylan", "Connor", "Ryan", "Nathan", "Cole", "Jaxon", "Parker", "Eli",
    "Declan", "Kieran", "Miles", "Caleb", "Roman", "Emmett", "Asher", "Levi", "Brady", "Griffin",
    "Nolan", "Sawyer", "Gavin", "Micah", "Tristan", "Julian", "Chase", "Brody", "Bennett", "Tobias",
    "Kai", "Dominic", "Sebastian", "Archer", "Damian", "Finley", "Reid", "Matteo", "Silas", "Jude",
    "Marek", "Andrei", "Nikita", "Ilya", "Viktor", "Teemu", "Mikael", "Anton", "Rasmus", "Ville",
    "Henrik", "Jesper", "Lukas", "Patrik", "Sami", "Joel", "Filip", "Elias", "Mikko", "Jani",
    "Adam", "Ben", "Brock", "Brendan", "Colton", "Devon", "Drew", "Eric", "Evan", "Frank",
    "Gabe", "Hayden", "Ian", "Jack", "Jake", "Jesse", "Joel", "Jonah", "Jordan", "Josh",
    "Kasper", "Kevin", "Kristian", "Lane", "Leo", "Marc", "Mark", "Max", "Neil", "Nick",
    "Oliver", "Oscar", "Otto", "Paavo", "Pavel", "Philip", "Quentin", "Riley", "Sam", "Shane",
    "Tanner", "Taylor", "Theo", "Tommy", "Vince", "Vlad", "William", "Yuri", "Zach", "Zane",
    "Abel", "Albin", "Alec", "Alessio", "Amir", "Anson", "Aron", "Artur", "August", "Axel",
    "Basil", "Beck", "Blaine", "Bo", "Boris", "Brant", "Bryce", "Cael", "Caden", "Cedric",
    "Cian", "Clyde", "Corbin", "Cosmo", "Dale", "Damon", "Dario", "Darcy", "Dax", "Denis",
    "Dimitri", "Dorian", "Duke", "Edvin", "Elian", "Enzo", "Evan", "Felix", "Finn", "Flynn",
    "Fraser", "Freddie", "Gael", "Gareth", "Gino", "Gordon", "Grady", "Grant", "Greer", "Hale",
    "Harlan", "Hector", "Henri", "Hugo", "Ira", "Isak", "Ivor", "Jace", "Jalen", "Jasper",
    "Jens", "Jonas", "Julius", "Karson", "Keaton", "Kellen", "Kian", "Klaus", "Koda", "Kurt",
    "Lars", "Lennox", "Loren", "Louie", "Lucian", "Mads", "Magnus", "Marlon", "Matias", "Milo",
    "Nash", "Nico", "Nils", "Noel", "Odin", "Orion", "Orson", "Oswin", "Otis", "Pierce",
    "Quincy", "Raul", "Remy", "Rene", "Rhett", "Ronan", "Rory", "Ruben", "Rune", "Sacha",
    "Soren", "Stellan", "Sven", "Thiago", "Tobin", "Torin", "Troy", "Umar", "Urban", "Valen",
    "Vaughn", "Wade", "Wes", "Xavier", "Yanis", "Zaire", "Zion",
    }
)

LAST_NAMES = sorted(
    {
    "Anderson", "Bennett", "Brodeur", "Carter", "Dalton", "Ellis", "Foster", "Graves", "Hughes", "Irwin", "Jensen",
    "Keller", "Lawson", "Morrison", "Nash", "Olsen", "Peterson", "Quinn", "Richards", "Sullivan", "Turner",
    "Underwood", "Vaughn", "Walker", "Xenos", "Young", "Zimmer", "Baranov", "Chekhov", "Dvorak", "Eriksson",
    "Fedorov", "Grimaldi", "Hartikainen", "Ivanov", "Johansson", "Kovalenko", "Lundqvist", "Malkin", "Novak", "Orlov",
    "Pavlov", "Romanov", "Soderberg", "Tarasenko", "Ulrich", "Volkov", "Wikstrom", "Yakovlev", "Zaitsev", "Aalto",
    "Bergman", "Carlsson", "Dahl", "Engstrom", "Franzen", "Gustafsson", "Holm", "Isaksson", "Lindholm", "Marklund",
    "Niemi", "Ojarvi", "Peltonen", "Rantanen", "Salonen", "Toivonen", "Uronen", "Virtanen", "Wallin", "Aho",
    "Adams", "Baker", "Bishop", "Blake", "Boone", "Brooks", "Bryant", "Burke", "Caldwell", "Campbell",
    "Clements", "Cook", "Cooper", "Cross", "Daniels", "Dawson", "Doyle", "Drake", "Duncan", "Edwards",
    "Farrell", "Fleming", "Ford", "Francis", "Garland", "Gibson", "Gordon", "Hansen", "Harris", "Henderson",
    "Holland", "Hudson", "Kane", "Knight", "Lambert", "Larsson", "Mason", "Mayer", "McBride", "McLean",
    "Mercer", "Meyer", "Miller", "Norris", "Parker", "Peters", "Riley", "Robertson", "Ross", "Sampson",
    "Sandin", "Strom", "Tanner", "Thompson", "Tierney", "Warren", "Watson", "West", "Wilson", "Wright",
    "Abbott", "Ahlgren", "Ainsley", "Aldridge", "Alvarez", "Amundsen", "Archer", "Arvidsson", "Atkins", "Avery",
    "Baldwin", "Ballard", "Barclay", "Barrett", "Barton", "Becker", "Bellamy", "Berg", "Bernier", "Bissett",
    "Blackwood", "Blythe", "Bodin", "Boucher", "Bowen", "Boyle", "Brandt", "Braun", "Briggs", "Brockman",
    "Calder", "Callahan", "Carlsen", "Carver", "Chandler", "Chapman", "Clarke", "Conley", "Conrad", "Corbett",
    "Costello", "Crosby", "Delaney", "Demers", "Donovan", "Dorn", "Draper", "Dreyer", "Eckert", "Eklund",
    "Emerson", "Fairchild", "Falk", "Faulkner", "Fenwick", "Fisher", "Fitzpatrick", "Foley", "Forster", "Frost",
    "Gallagher", "Gamble", "Garrett", "Gauthier", "Geller", "Gentry", "Gilroy", "Goodwin", "Graham", "Grant",
    "Greene", "Grier", "Hale", "Halloran", "Harding", "Harper", "Hart", "Hastings", "Hawkins", "Heller",
    "Henley", "Hobbs", "Hoffman", "Holt", "Horvath", "Howe", "Hugheson", "Iverson", "Jamison", "Kendrick",
    "Kingsley", "Kirk", "Kline", "Kovacs", "Kramer", "Lachance", "Laird", "Lang", "Larkin", "Larsen",
    "Leclerc", "Lennon", "Leroux", "Locke", "Lowell", "Lutz", "Madden", "Maddox", "Mahoney", "Malloy",
    "Mantha", "Marin", "Marsden", "Matson", "McAllister", "McClure", "McNabb", "Mercier", "Michaels", "Monroe",
    "Morin", "Morrow", "Nadeau", "Neville", "North", "Oakes", "Osborne", "Parsons", "Paxton", "Payne",
    "Pearce", "Poitras", "Prescott", "Quaid", "Quinlan", "Radek", "Rafferty", "Ramsay", "Reardon", "Redmond",
    "Reeves", "Renard", "Renaud", "Ritchie", "Rooney", "Rowe", "Ryder", "Sanders", "Sauer", "Sawyer", "Schultz",
    "Shaw", "Shepard", "Sinclair", "Sloan", "Spencer", "Stanton", "Sterling", "Stone", "Swan", "Talon",
    "Temple", "Thorne", "Tobin", "Townsend", "Trask", "Trent", "Turnbull", "Valois", "Vickers", "Ward",
    "Whitman", "Wilder", "Willis", "Winslow", "Wolfe", "Yates", "York", "Zeller",
    }
)

COUNTRY_FIRST_NAMES: dict[str, tuple[str, ...]] = {
    "CA": ("Adam", "Alex", "Brock", "Carter", "Connor", "Dylan", "Ethan", "Gavin", "Hudson", "Liam", "Logan", "Mason", "Noah", "Owen", "Parker", "Ryan"),
    "US": ("Aiden", "Ben", "Caleb", "Chase", "Cole", "Eli", "Emmett", "Griffin", "Hayden", "Jack", "Jake", "Jeffrey", "Levi", "Miles", "Nolan", "Sawyer", "Wyatt"),
    "SE": ("Albin", "Axel", "Elias", "Henrik", "Isak", "Jesper", "Johan", "Lars", "Lukas", "Mikael", "Nils", "Oskar", "Rasmus", "Soren", "Viktor", "Ville"),
    "FI": ("Elias", "Henri", "Jani", "Joel", "Kasper", "Lauri", "Mikael", "Mikko", "Niko", "Otto", "Patrik", "Roope", "Sami", "Teemu", "Valtteri", "Ville"),
    "RU": ("Andrei", "Artem", "Dimitri", "Ilya", "Ivan", "Kirill", "Maksim", "Mikhail", "Nikita", "Pavel", "Roman", "Sergei", "Viktor", "Vlad", "Yuri", "Zhenya"),
    "CZ": ("Adam", "Daniel", "David", "Dominik", "Filip", "Jakub", "Jan", "Jiri", "Lukas", "Martin", "Milan", "Miroslav", "Ondrej", "Pavel", "Radek", "Tomas"),
    "SK": ("Adam", "Dominik", "Filip", "Juraj", "Kristian", "Lukas", "Martin", "Matej", "Marek", "Michal", "Milan", "Patrik", "Peter", "Richard", "Samuel", "Tomas"),
    "DE": ("Anton", "Ben", "Dominik", "Felix", "Finn", "Jan", "Jonas", "Kevin", "Leon", "Lukas", "Marco", "Max", "Moritz", "Niklas", "Philip", "Tobias"),
    "CH": ("Andreas", "Dominik", "Fabian", "Janis", "Kevin", "Lars", "Luca", "Lukas", "Marco", "Matias", "Nico", "Noel", "Roman", "Sandro", "Simon", "Timo"),
    "LV": ("Artur", "Davis", "Denis", "Edgars", "Kristaps", "Miks", "Nauris", "Nikita", "Oskars", "Rihards", "Roberts", "Rudolfs", "Sandis", "Teodors", "Uvis", "Viktors"),
    "DK": ("Anders", "Emil", "Frederik", "Jeppe", "Jonas", "Kasper", "Kristian", "Lars", "Magnus", "Mikkel", "Nikolaj", "Oliver", "Rasmus", "Soren", "Thomas", "Viktor"),
    "LT": ("Arnas", "Darius", "Dominykas", "Edvinas", "Ignas", "Jokubas", "Jonas", "Justinas", "Karolis", "Linas", "Lukas", "Mantas", "Matas", "Paulius", "Rokas", "Tomas", "Vilius"),
    "NO": ("Andreas", "Eirik", "Emil", "Erik", "Fredrik", "Henrik", "Kristian", "Lars", "Magnus", "Marius", "Martin", "Mats", "Nikolai", "Oskar", "Sander", "Tobias"),
    "BY": ("Alexei", "Andrei", "Artem", "Dmitri", "Egor", "Ilya", "Kirill", "Maksim", "Mikhail", "Nikita", "Pavel", "Roman", "Sergei", "Viktor", "Vladislav", "Yegor"),
    "SI": ("Anze", "Blaz", "Filip", "Jan", "Jure", "Luka", "Mark", "Matej", "Miha", "Nejc", "Rok", "Tadej", "Tim", "Urban", "Vid", "Zan"),
    "AT": ("Alexander", "Andreas", "Christoph", "Daniel", "David", "Dominik", "Felix", "Florian", "Lukas", "Marco", "Matthias", "Michael", "Niklas", "Raphael", "Stefan", "Thomas"),
    "FR": ("Alexandre", "Antoine", "Bastien", "Clement", "Damien", "Etienne", "Hugo", "Julien", "Louis", "Mathieu", "Maxime", "Nicolas", "Pierre", "Quentin", "Theo", "Vincent"),
}

COUNTRY_LAST_NAMES: dict[str, tuple[str, ...]] = {
    "CA": ("Anderson", "Bennett", "Brooks", "Campbell", "Carter", "Cooper", "Dawson", "Edwards", "Farrell", "Foster", "Gibson", "Hughes", "Lawson", "McBride", "Turner", "Watson"),
    "US": ("Abbott", "Baker", "Bishop", "Bryant", "Caldwell", "Cross", "Duncan", "Graham", "Harris", "Henderson", "Knight", "Miller", "Parker", "Ross", "Sanders", "Spencer", "Wright"),
    "SE": ("Ahlgren", "Berg", "Carlsson", "Dahl", "Engstrom", "Gustafsson", "Holm", "Isaksson", "Johansson", "Lindholm", "Marklund", "Sandin", "Soderberg", "Wallin", "Wikstrom", "Yates"),
    "FI": ("Aalto", "Aho", "Hartikainen", "Niemi", "Ojarvi", "Peltonen", "Rantanen", "Salonen", "Toivonen", "Uronen", "Virtanen", "Kirk", "Mayer", "Nadeau", "North", "Stone"),
    "RU": ("Baranov", "Chekhov", "Fedorov", "Ivanov", "Kovalenko", "Malkin", "Orlov", "Pavlov", "Romanov", "Tarasenko", "Volkov", "Yakovlev", "Zaitsev", "Kovacs", "Morin", "Novak"),
    "CZ": ("Dvorak", "Kovacs", "Lachance", "Leroux", "Novak", "Poitras", "Radek", "Renaud", "Ritchie", "Trent", "Valois", "Zeller", "Draper", "Eklund", "Faulkner", "Quinlan"),
    "SK": ("Demers", "Heller", "Kline", "Maddox", "Mercer", "Meyer", "Pavlov", "Prescott", "Quaid", "Reardon", "Ryder", "Sauer", "Strom", "Temple", "Tobin", "Turnbull"),
    "DE": ("Bergman", "Braun", "Dreyer", "Eckert", "Engstrom", "Frost", "Heller", "Hoffman", "Kramer", "Lang", "Lutz", "Meyer", "Schultz", "Ulrich", "Wilder", "Zimmer"),
    "CH": ("Avery", "Becker", "Bernier", "Conrad", "Forster", "Gallagher", "Geller", "Kingsley", "Kline", "Leclerc", "Mason", "Mercier", "Norris", "Renard", "Renaud", "Sterling"),
    "LV": ("Arvidsson", "Bissett", "Dorn", "Edwards", "Geller", "Henley", "Iverson", "Kendrick", "Larsen", "Malloy", "Nadeau", "Paxton", "Rafferty", "Sawyer", "Trask", "Vickers"),
    "DK": ("Bodin", "Callahan", "Clarke", "Donovan", "Forster", "Gentry", "Henley", "Jensen", "Lennon", "Lowell", "Madsen", "Morrow", "Parsons", "Rowe", "Stanton", "Whitman"),
    "LT": ("Darius", "Gineitis", "Jankauskas", "Kazlauskas", "Lukauskas", "Maciulis", "Petrauskas", "Rimkus", "Sabonis", "Stankevicius", "Urbonas", "Vaitkus", "Zukauskas", "Aukstaitis", "Baltrunas", "Mockus"),
    "NO": ("Berg", "Dahl", "Eik", "Foss", "Gundersen", "Hagen", "Haugen", "Kristoffersen", "Larsen", "Lie", "Moe", "Nilsen", "Olsen", "Sande", "Solberg", "Thorsen"),
    "BY": ("Baranov", "Belov", "Dragun", "Ivanov", "Kovalev", "Malkin", "Petrov", "Romanov", "Sidorov", "Tarasenko", "Volkov", "Yakovlev", "Zhukov", "Karpov", "Mironov", "Nikitin"),
    "SI": ("Kovacic", "Kranjc", "Lah", "Matic", "Novak", "Pintar", "Potochnik", "Pretnar", "Rozman", "Skof", "Snoj", "Strnad", "Vidmar", "Zagar", "Zajc", "Zorc"),
    "AT": ("Auer", "Baumgartner", "Bichler", "Eder", "Gruber", "Hofer", "Huber", "Kainz", "Koller", "Leitner", "Lindner", "Moser", "Pichler", "Steiner", "Wagner", "Zimmermann"),
    "FR": ("Bernard", "Blanc", "Chevalier", "Dubois", "Dupont", "Faure", "Fournier", "Garreau", "Girard", "Laurent", "Lefevre", "Mercier", "Moreau", "Petit", "Roux", "Vasseur"),
}

COUNTRY_NAME_WEIGHTS: dict[str, float] = {
    "CA": 0.34,
    "US": 0.225,
    "SE": 0.08,
    "FI": 0.06,
    "RU": 0.08,
    "CZ": 0.05,
    "SK": 0.03,
    "DE": 0.03,
    "CH": 0.03,
    "LV": 0.02,
    "DK": 0.02,
    "LT": 0.01,
    "NO": 0.005,
    "BY": 0.005,
    "SI": 0.005,
    "AT": 0.005,
    "FR": 0.005,
}

UNIQUE_CA_LAST_NAMES = {"Brodeur"}
UNIQUE_US_LAST_NAMES = {"Sanders"}


def _pick_weighted_country(rng: random.Random, weights: dict[str, float]) -> str:
    roll = rng.random()
    cumulative = 0.0
    last_code = "CA"
    for code, weight in weights.items():
        cumulative += weight
        last_code = code
        if roll <= cumulative:
            return code
    return last_code


def _expand_country_name_map(
    base: dict[str, tuple[str, ...]],
    all_names: list[str],
    weights: dict[str, float],
    seed: int,
) -> dict[str, tuple[str, ...]]:
    # Keep explicit country assignments (including cross-country overlaps),
    # then assign any remaining generic names to one country for wider variation.
    mapped: dict[str, set[str]] = {code: set(names) for code, names in base.items()}
    assigned = {name for names in mapped.values() for name in names}
    unassigned = [name for name in all_names if name not in assigned]
    rng = random.Random(seed)
    for name in unassigned:
        code = _pick_weighted_country(rng, weights)
        mapped.setdefault(code, set()).add(name)
    return {code: tuple(sorted(names)) for code, names in mapped.items()}

def _normalize_na_first_names(base: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    mapped = {code: tuple(names) for code, names in base.items()}
    ca_names = set(mapped.get("CA", ()))
    us_names = set(mapped.get("US", ()))
    shared = tuple(sorted(ca_names | us_names))
    mapped["CA"] = shared
    mapped["US"] = shared
    return mapped

def _normalize_na_last_names(base: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    mapped = {code: tuple(names) for code, names in base.items()}
    ca_names = set(mapped.get("CA", ()))
    us_names = set(mapped.get("US", ()))
    shared = (ca_names | us_names) - UNIQUE_CA_LAST_NAMES - UNIQUE_US_LAST_NAMES
    mapped["CA"] = tuple(sorted(shared | UNIQUE_CA_LAST_NAMES))
    mapped["US"] = tuple(sorted(shared | UNIQUE_US_LAST_NAMES))
    return mapped


class NameGenerator:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._used: set[str] = set()
        self._pool = [f"{first} {last}" for first in FIRST_NAMES for last in LAST_NAMES]
        self._rng.shuffle(self._pool)
        self._idx = 0
        self._country_pools: dict[str, list[str]] = {}
        self._country_idx: dict[str, int] = {}
        normalized_first_names = _normalize_na_first_names(COUNTRY_FIRST_NAMES)
        normalized_last_names = _normalize_na_last_names(COUNTRY_LAST_NAMES)
        expanded_first_names = _expand_country_name_map(
            normalized_first_names,
            FIRST_NAMES,
            COUNTRY_NAME_WEIGHTS,
            101,
        )
        expanded_last_names = _expand_country_name_map(
            normalized_last_names,
            LAST_NAMES,
            COUNTRY_NAME_WEIGHTS,
            202,
        )
        for code, firsts in expanded_first_names.items():
            lasts = expanded_last_names.get(code, tuple(LAST_NAMES))
            pool = [f"{first} {last}" for first in sorted(set(firsts)) for last in sorted(set(lasts))]
            self._rng.shuffle(pool)
            self._country_pools[code] = pool
            self._country_idx[code] = 0

    def reserve(self, names: list[str]) -> None:
        self._used.update(names)

    def _next_from_pool(self, pool: list[str], idx_key: str) -> str | None:
        if idx_key == "global":
            idx = self._idx
            while idx < len(pool):
                name = pool[idx]
                idx += 1
                if name not in self._used:
                    self._used.add(name)
                    self._idx = idx
                    return name
            self._idx = idx
            return None
        idx = self._country_idx.get(idx_key, 0)
        while idx < len(pool):
            name = pool[idx]
            idx += 1
            if name not in self._used:
                self._used.add(name)
                self._country_idx[idx_key] = idx
                return name
        self._country_idx[idx_key] = idx
        return None

    def next_name(self, country_code: str | None = None) -> str:
        code = str(country_code or "").upper().strip()
        if code in self._country_pools:
            name = self._next_from_pool(self._country_pools[code], code)
            if name:
                return name

        name = self._next_from_pool(self._pool, "global")
        if name:
            return name

        suffix = 1
        base_pool = self._country_pools.get(code, self._pool)
        while True:
            base = base_pool[self._rng.randrange(0, len(base_pool))]
            candidate = f"{base} {suffix}"
            if candidate not in self._used:
                self._used.add(candidate)
                return candidate
            suffix += 1
