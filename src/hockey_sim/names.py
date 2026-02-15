from __future__ import annotations

import random

FIRST_NAMES = [
    "Alex", "Noah", "Liam", "Ethan", "Lucas", "Mason", "Logan", "Aiden", "Owen", "Wyatt",
    "Carter", "Hudson", "Dylan", "Connor", "Ryan", "Nathan", "Cole", "Jaxon", "Parker", "Eli",
    "Declan", "Kieran", "Miles", "Caleb", "Roman", "Emmett", "Asher", "Levi", "Brady", "Griffin",
    "Nolan", "Sawyer", "Gavin", "Micah", "Tristan", "Julian", "Chase", "Brody", "Bennett", "Tobias",
    "Kai", "Dominic", "Sebastian", "Archer", "Damian", "Finley", "Reid", "Matteo", "Silas", "Jude",
    "Marek", "Andrei", "Nikita", "Ilya", "Viktor", "Teemu", "Mikael", "Anton", "Rasmus", "Ville",
    "Henrik", "Jesper", "Lukas", "Patrik", "Sami", "Joel", "Filip", "Elias", "Mikko", "Jani",
]

LAST_NAMES = [
    "Anderson", "Bennett", "Carter", "Dalton", "Ellis", "Foster", "Graves", "Hughes", "Irwin", "Jensen",
    "Keller", "Lawson", "Morrison", "Nash", "Olsen", "Peterson", "Quinn", "Richards", "Sullivan", "Turner",
    "Underwood", "Vaughn", "Walker", "Xenos", "Young", "Zimmer", "Baranov", "Chekhov", "Dvorak", "Eriksson",
    "Fedorov", "Grimaldi", "Hartikainen", "Ivanov", "Johansson", "Kovalenko", "Lundqvist", "Malkin", "Novak", "Orlov",
    "Pavlov", "Romanov", "Soderberg", "Tarasenko", "Ulrich", "Volkov", "Wikstrom", "Yakovlev", "Zaitsev", "Aalto",
    "Bergman", "Carlsson", "Dahl", "Engstrom", "Franzen", "Gustafsson", "Holm", "Isaksson", "Lindholm", "Marklund",
    "Niemi", "Ojarvi", "Peltonen", "Rantanen", "Salonen", "Toivonen", "Uronen", "Virtanen", "Wallin", "Aho",
]

FIRST_NAMES.extend(
    [
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
    ]
)

LAST_NAMES.extend(
    [
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
        "Reeves", "Renard", "Renaud", "Ritchie", "Rooney", "Rowe", "Ryder", "Sauer", "Sawyer", "Schultz",
        "Shaw", "Shepard", "Sinclair", "Sloan", "Spencer", "Stanton", "Sterling", "Stone", "Swan", "Talon",
        "Temple", "Thorne", "Tobin", "Townsend", "Trask", "Trent", "Turnbull", "Valois", "Vickers", "Ward",
        "Whitman", "Wilder", "Willis", "Winslow", "Wolfe", "Yates", "York", "Zeller",
    ]
)


class NameGenerator:
    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._used: set[str] = set()
        self._pool = [f"{first} {last}" for first in FIRST_NAMES for last in LAST_NAMES]
        self._rng.shuffle(self._pool)
        self._idx = 0

    def reserve(self, names: list[str]) -> None:
        self._used.update(names)

    def next_name(self) -> str:
        while self._idx < len(self._pool):
            name = self._pool[self._idx]
            self._idx += 1
            if name not in self._used:
                self._used.add(name)
                return name

        suffix = 1
        while True:
            base = self._pool[self._rng.randrange(0, len(self._pool))]
            candidate = f"{base} {suffix}"
            if candidate not in self._used:
                self._used.add(candidate)
                return candidate
            suffix += 1
