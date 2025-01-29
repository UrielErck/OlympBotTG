import requests as rq
from lxml import html
from OlympClass import *


def parce():
    CountFrom = 0
    domain = "https://olimpiada.ru"
    response = rq.Response

    debug = True

    OlympsList = []

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
            eventBloksList = OlympPageTree.xpath('.//tbody//tr[@data="none"]')
            for i in eventBloksList:
                title = i.xpath('.//td[1]//a//div')[0].text_content()
                rawDateData: str = i.xpath('.//td[2]//a')[0].text_content().lower()
                print(f'{title} | {rawDateData}')
                if 'до' in rawDateData:
                    pass
                    # time range without start

                elif '...' in rawDateData:
                    pass
                    # determined time range
                else:
                    pass
                    # determined date


            OlympsList.append(olympiad)
            # print(olympiad, end=f'\n-----------\n')




