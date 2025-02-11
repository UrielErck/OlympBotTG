class Olympiad:
    Name: str
    ID: int
    Level: int # from 1 (hardest) to 3 (easy one) or -1 if not in list of Минобрнауки
    Rating: float
    Description: str
    Link: str
    Image: str # Web link to image
    Subject: list[str] # list of names
    Events: list[dict]
    # Type: str # may be 9 (squad), ind (individual), dist (distant), any (WIP)
    # Date: dict or -1 # start and end in unix format or -1 if indefinitely
    # IsVisitingSchool: bool

    def __str__(self):
        return f'''
Olympiad name: {self.Name}
ID: {self.ID} | Subjects: {self.Subject}
Description: {self.Description}
Link: {self.Link}
Level: {self.Level}
'''

    def __init__(self):
        pass