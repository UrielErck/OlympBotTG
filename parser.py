import requests as rq
from lxml import html
from OlympClass import *
from datetime import datetime
import time
import sqlite3
import json


def parce(SQLBase: sqlite3.Connection) -> None:
    """
    Save into given DB table of olympiads from site olimpiada.ru
    Read more into:
    `Obsidian note <documentation.md>`_
    :param SQLBase:
    :return: None
    """
    CountFrom = 0
    domain = "https://olimpiada.ru"
    response = rq.Response

    debug = True

    SQLBaseCursor = SQLBase.cursor()
    SQLBaseCursor.execute(f'''
                CREATE TABLE IF NOT EXISTS Olympiads (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                level INTEGER NOT NULL,
                rating REAL NOT NULL,
                description TEXT NOT NULL,
                link TEXT NOT NULL,
                image_link TEXT NOT NULL,
                subjects TEXT NOT NULL
                )
                ''')
    # SQLBaseCursor.execute(f'''
    #                 CREATE TABLE IF NOT EXISTS Events (
    #                 id INTEGER PRIMARY KEY,
    #                 olymp_id INTEGER NOT NULL
    #                 name TEXT NOT NULL,
    #                 type TEXT NOT NULL,
    #                 start_date INTEGER NOT NULL,
    #                 end_date INTEGER NOT NULL
    #                 )
    #                 ''')

    while response.text != 'stop':
        BaseSite = f'https://olimpiada.ru/include/activity/megalist.php?cnow={CountFrom}'
        try:
            response = rq.get(BaseSite)
        except Exception:
            print('Meet error')
            exit(-1)
        tree = html.fromstring(response.text)

        CountFrom += 11
        if debug: print(f'Parsing progress: {CountFrom}', response, sep='\n')
        for OlympiadsMainDiv in tree.xpath('./div[@class = "fav_olimp olimpiada "]'):

            # Creating object
            olympiad = Olympiad()

            # Filtering data
            OlympsDataDiv = OlympiadsMainDiv.xpath('./div[@class = "o-block"]')[0]
            OlympsDataInfoDiv = OlympsDataDiv.xpath('./div[@class = "o-info"]')[0]

            # Set object`s values
            olympiad.Name = OlympsDataInfoDiv.xpath('./a[@class = "none_a black"][1]/span[@class = "headline"][1]')[0].text
            olympiad.Link = domain + OlympsDataInfoDiv.xpath('./a[@class = "none_a black"][1]')[0].get('href')
            print(f'Olympiad Link: {olympiad.Link}')

            # Parsing olympiad`s main page
            # Creating parce response
            OlympPageResponse = rq.get(olympiad.Link)
            OlympPageTree = html.fromstring(OlympPageResponse.text)

            # Add ID from URL
            olympiad.ID = int(olympiad.Link.split('/')[-1])

            # Parsing subject list from olympiad page
            def stringPrep(string:str):
                string = string.replace(u'\xa0', ' ')
                string = string[1:]
                return string
            subject = [stringPrep(elem.text_content()) for elem in OlympPageTree.xpath('.//div[@class="subject_tags_full"]/span')]
            olympiad.Subject = subject

            # Parsing rating
            rating = OlympPageTree.xpath('.//div[@class="mact_rating"]/span[@class="rating"]')
            if rating:
                rating = float(rating[0].text.replace(",", "."))
            olympiad.Rating = rating

            # Parsing description
            description = OlympPageTree.xpath('.//div[@class="info block_with_margin_bottom"]/p')
            if description:
                description = description[0].text
            olympiad.Description = description

            # Parsing image link
            ImageObject = OlympPageTree.xpath('.//div[@id="white_container"]/div[1]/img[1]')
            if ImageObject:
                olympiad.Image = domain + ImageObject[0].get('src')
            else:
                olympiad.Image = None

            # Level of complexity
            TextBlocks = OlympPageTree.xpath('.//div[@class=" f_blocks"]')
            Level = -1
            for i in TextBlocks:
                title = i.xpath('.//span')[0].text_content()
                if title == 'В Перечне Минобрнауки':
                    textToFind = 'уровень '
                    blockText: str = i.text_content()
                    textIndex = blockText.find(textToFind) + len(textToFind)
                    Level = blockText[textIndex: textIndex+1]
            olympiad.Level = Level

            # Events list
            Events: list = []
            eventBloksList = OlympPageTree.xpath('.//tbody//tr[@data="none"]')
            for i, index in zip(eventBloksList, range(len(eventBloksList))):
                i: html
                title = i.xpath('.//td[1]//a//div')[0].text
                rawDateData: str = i.xpath('.//td[2]//a')[0].text_content().lower()
                rawDateData = rawDateData.replace('\xa0', ' ')
                todayDate = datetime.now()
                if i.get("class") == 'grey':
                    # Date has passed away
                    isEventPassed = True
                else:
                    # It`s going or will be
                    isEventPassed = False

                def repairDate(
                        strDate: str,
                        isPassed: bool = None,
                        currentDate: datetime = None,
                ) -> datetime:
                    MonthDict = {
                        'янв': 1,
                        'фев': 2,
                        'мар': 3,
                        'апр': 4,
                        'мая': 5, 'май':5,
                        'июн': 6,
                        'июл': 7,
                        'авг': 8,
                        'сен': 9,
                        'окт': 10,
                        'ноя': 11,
                        'дек': 12,
                    }
                    listStrDate = strDate.replace('\xa0', ' ').split(' ')
                    # print(listStrDate)
                    # if listStrDate[0].lower() == 'уточняется':
                    day = int(listStrDate[0])
                    month = MonthDict[listStrDate[1]]
                    eventDate = datetime(day=day, month=month, year=currentDate.year)
                    if (eventDate < todayDate) != isPassed:
                        eventDate = datetime(day=day, month=month, year=currentDate.year-1)
                    return eventDate

                if 'до' in rawDateData:
                    # time range without start
                    strDate = rawDateData.split('до ')[1]
                    # print(f'Date format: 1\nDate before: {rawDateData}\nDate after: {strDate }')
                    # print(strDate)
                    if strDate == 'уточняется':
                        print("Event date is not defined, skipping")
                        continue
                    Date: datetime = repairDate(strDate, isEventPassed, todayDate)
                    eventDict = {
                        "ID": index,
                        "DateType": "noStart",
                        "Name": title,
                        "startDate": -1,
                        "endDate": time.mktime(Date.timetuple()),
                    }

                elif '...' in rawDateData:
                    # determined time range
                    rawDate: list = rawDateData.split('...')
                    # print(rawDate)
                    if not ' ' in rawDate[0]:
                        rawDate[0] = f"{rawDate[0]} {rawDate[1].split(' ')[1]}"
                    if 'уточняется' in rawDate:
                        print("Event date is not defined, skipping")
                        continue
                    Date: list[datetime] = [repairDate(i, isEventPassed, todayDate) for i in rawDate]
                    # print(f'Date type: determined range | Start: {Date[0]} End: {Date[1]}')
                    eventDict = {
                        "ID": index,
                        "DateType": "DeterminedRange",
                        "Name": title,
                        "startDate": time.mktime(Date[0].timetuple()),
                        "endDate": time.mktime(Date[1].timetuple()),
                    }

                else:
                    # determined date
                    strDate = rawDateData
                    if strDate == 'уточняется':
                        print("Event date is not defined, skipping")
                        continue
                    Date: datetime = repairDate(strDate, isEventPassed, todayDate)
                    eventDict = {
                        "ID": index,
                        "DateType": "DeterminedDate",
                        "Name": title,
                        "startDate": time.mktime(Date.timetuple()),
                        "endDate": -1,
                    }
#                 # Save olympiad`s event to db
#                 SQLBaseCursor.execute(f"""
#                 INSERT OR REPLACE INTO Events
#                 (id, olymp_id, name, type, start_date, end_date)
#                 VALUES
#                 (?, ?, ?, ?, ?, ?)
# """, (
#                     int(eventDict['ID']),
#                     int(olympiad.ID),
#                     str(eventDict['Name']),
#                     str(eventDict['type']),
#                     int(eventDict['start_date']),
#                     int(eventDict['end_date']),
#                 ))
#                 SQLBase.commit()
#
            olympiad.Events = Events

            #Save element to the base
            SQLBaseCursor.execute(f'''
            INSERT OR REPLACE INTO Olympiads 
            (id, name, level, rating, description, link, image_link, subjects, events)
            VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                int(olympiad.ID),
                str(olympiad.Name),
                int(olympiad.Level),
                float(olympiad.Rating),
                str(olympiad.Description),
                str(olympiad.Link),
                str(olympiad.Image),
                str(json.dumps(olympiad.Subject)),
                str(json.dumps(olympiad.Events)),
            ))
            SQLBase.commit()

            print(olympiad, end=f'\n-----------\n')
    # Close base and end work
    SQLBase.close()
