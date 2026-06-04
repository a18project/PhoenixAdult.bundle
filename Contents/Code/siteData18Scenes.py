import PAsearchSites
import PAutils
import networkReptyle
from PAdata18ImageSearch import getData18Images


def first_text(elements, default=''):
    if elements:
        return elements[0].text_content().strip()
    return default


def get_xpath_text(root, path, default=''):
    try:
        return first_text(root.xpath(path), default)
    except:
        return default


def compute_score(sceneID, urlID, searchData, title, releaseDate):
    if sceneID == urlID:
        return 100

    if searchData.date and releaseDate:
        return 80 - Util.LevenshteinDistance(searchData.date, releaseDate)

    return 80 - Util.LevenshteinDistance(searchData.title.lower(), title.lower().replace('-', ' ').replace("'", ''))


def search(results, lang, siteNum, searchData):
    searchResults = []
    siteResults = []
    temp = []
    count = 0
    cookies = {'data_user_captcha': '1'}
    headers = {'Referer': 'https://www.data18.com'}

    # Scene ID detection
    sceneID = None
    parts = searchData.title.split()
    if unicode(parts[0], 'UTF-8').isdigit():
        sceneID = parts[0]
        if int(sceneID) > 100:
            searchData.title = searchData.title.replace(sceneID, '', 1).strip()
            sceneURL = '%s/scenes/%s' % (PAsearchSites.getSearchBaseURL(siteNum), sceneID)
            searchResults.append(sceneURL)

    # Clean search query
    searchData.encoded = re.sub(r'[^\w|^\s]', '', searchData.title)
    baseSearchURL = PAsearchSites.getSearchSearchURL(siteNum)
    searchURL = '%s%s&key2=%s&next=1&page=0' % (baseSearchURL, searchData.encoded, searchData.encoded)

    req = PAutils.HTTPRequest(searchURL, headers=headers, cookies=cookies)
    searchPageElements = HTML.ElementFromString(req.text)

    # Page count
    match = re.search(r'(?<=pages:\s).*(?=])', req.text)
    numPages = min(int(match.group(0)), 10) if match else 1

    # Loop through search pages
    for idx in range(numPages):
        for node in searchPageElements.xpath('//a'):
            sceneURL = node.xpath('./@href')[0]
            if '/scenes/' not in sceneURL or sceneURL in searchResults:
                continue

            urlID = re.sub(r'.*/', '', sceneURL)
            siteDisplay = get_xpath_text(node, './/i', '')
            title = get_xpath_text(node, './/p[@class="gen12 bold"]')
            curID = PAutils.Encode(sceneURL)

            # If truncated title, treat differently
            if '...' in title:
                searchResults.append(sceneURL)
                continue

            siteResults.append(sceneURL)

            dateText = get_xpath_text(node, './/span[@class="gen11"]/text()', '')
            if dateText and dateText != 'unknown':
                releaseDate = datetime.strptime(dateText, "%B %d, %Y").strftime('%Y-%m-%d')
            else:
                releaseDate = searchData.dateFormat() if searchData.date else ''

            score = compute_score(sceneID, urlID, searchData, title, releaseDate)
            displayDate = releaseDate if dateText else ''

            resultObj = MetadataSearchResult(id='%s|%d|%s' % (curID, siteNum, releaseDate), name='%s [%s] %s' % (title, siteDisplay, displayDate), score=score, lang=lang)

            if score == 80:
                count += 1
                temp.append(resultObj)
            else:
                results.Append(resultObj)

        # Load next page
        if idx + 1 < numPages:
            nextURL = '%s%s&key2=%s&next=1&page=%d' % (
                baseSearchURL, searchData.encoded, searchData.encoded, idx + 1)
            req = PAutils.HTTPRequest(nextURL, headers=headers, cookies=cookies)
            searchPageElements = HTML.ElementFromString(req.text)

    # Google fallback
    googleResults = PAutils.getFromSearchEngine(searchData.title, siteNum)
    for sceneURL in googleResults:
        sceneURL = sceneURL.replace('/content/', '/scenes/').replace('http:', 'https:')
        if '/scenes/' in sceneURL and '.html' not in sceneURL and sceneURL not in searchResults and sceneURL not in siteResults:
            searchResults.append(sceneURL)

    # Process detail pages
    for sceneURL in searchResults:
        req = PAutils.HTTPRequest(sceneURL, cookies=cookies)
        detailsPageElements = HTML.ElementFromString(req.text)
        urlID = re.sub(r'.*/', '', sceneURL)

        if not detailsPageElements:
            Log('Possible IP BAN: Retry on VPN')
            break

        # Studio / Network
        siteName = ''
        studio_xpaths = [
            '//b[.="Studio"]/following::b[1]',
            '//b[.="Network"]/following::b[1]',
            '//b[.="Studio"]/following::a[1]',
            '//b[.="Network"]/following::a[1]',
            '//p[b[.="Site"]]/a'
        ]

        for path in studio_xpaths:
            result = detailsPageElements.xpath(path)
            if result:
                siteName = first_text(result)
                break

        subSite = get_xpath_text(detailsPageElements, '//p[b[.="Site"]]/following-sibling::a[@class="bold"][1]', '')

        siteDisplay = '%s/%s' % (siteName, subSite) if siteName and subSite else (siteName or subSite)

        title = PAutils.parseTitle(get_xpath_text(detailsPageElements, '//h1'), siteNum)
        curID = PAutils.Encode(sceneURL)

        dateText = get_xpath_text(detailsPageElements, '//span[contains(., "Release date")]/following::a/b[1]', '')
        if dateText and dateText != 'unknown':
            releaseDate = parse(dateText).strftime('%Y-%m-%d')
        else:
            releaseDate = searchData.dateFormat() if searchData.date else ''

        score = compute_score(sceneID, urlID, searchData, title, releaseDate)
        displayDate = releaseDate if dateText else ''

        if 'Error 404' not in title:
            resultObj = MetadataSearchResult(id='%s|%d|%s' % (curID, siteNum, releaseDate), name='%s [%s] %s' % (title, siteDisplay, displayDate), score=score, lang=lang)
            if score == 80:
                count += 1
                temp.append(resultObj)
            else:
                results.Append(resultObj)

    # Final scoring adjustments
    for r in temp:
        if count > 1 and r.score == 80:
            results.Append(MetadataSearchResult(id=r.id, name=r.name, score=79, lang=lang))
        else:
            results.Append(r)

    return results


def update(metadata, lang, siteNum, movieGenres, movieActors, movieCollections, art):
    metadata_id = str(metadata.id).split('|')
    sceneURL = PAutils.Decode(metadata_id[0])
    sceneDate = metadata_id[2]
    req = PAutils.HTTPRequest(sceneURL, cookies={'data_user_captcha': '1'})
    detailsPageElements = HTML.ElementFromString(req.text)

    if not detailsPageElements:
        Log('Possible IP BAN: Retry on VPN')
        return metadata

    # Title
    metadata.title = PAutils.parseTitle(detailsPageElements.xpath('//h1')[0].text_content(), siteNum)

    # Summary
    summary = ''
    summary_paths = [
        ('//div[@class="gen12"]/div[contains(., "Story")]', 'Story -'),
        ('//div[@class="gen12"]//div[@class="hideContent boxdesc" and contains(., "Description")]', '---'),
        ('//div[@class="gen12"]/div[contains(., "Movie Description")]', '--'),
    ]

    for xpath, splitter in summary_paths:
        result = detailsPageElements.xpath(xpath)
        if result:
            summary = first_text(result).rsplit(splitter)[-1].strip()
            break

    metadata.summary = summary

    # Studio
    studio = ''
    studio_xpaths = [
        '//b[.="Studio"]/following::b[1]',
        '//b[.="Network"]/following::b[1]',
        '//b[.="Studio"]/following::a[1]',
        '//b[.="Network"]/following::a[1]',
        '//p[b[.="Site"]]/a'
    ]

    for xpath in studio_xpaths:
        result = detailsPageElements.xpath(xpath)
        if result:
            studio = first_text(result)
            break

    # Tagline and Collection(s)
    siteName = first_text(detailsPageElements.xpath('//p[b[.="Site"]]/a'), default=None)

    # Subsite
    subSite = None
    subsite_a = detailsPageElements.xpath('//p[b[contains(., "Network")]]//a')

    if subsite_a:
        subSite = first_text(subsite_a)

    if subSite and subSite.lower() in ['brazzers', 'bangbros']:
        subsite_text = detailsPageElements.xpath('//b[contains(., "Network")]//following-sibling::text()')
        if len(subsite_text) > 2:
            candidate = subsite_text[2].split('|')[-1].strip()
            if candidate in ['Brazzers Exxtra', 'Brazzers Live', 'BangBros Clips']:
                subSite = candidate

    # Serie
    serieName = first_text(detailsPageElements.xpath('//p[contains(., "Webserie:") or contains(., "Miniserie:")]//text()[contains(., "Webserie:") or contains(., "Miniserie:")]/following::a[1]'), default=None)

    # Movie
    movieName = first_text(detailsPageElements.xpath('//p[contains(., "Movie:")]//text()[contains(., "Movie:")]/following::a[1]'), default=None)

    # Tagline
    tagline = ''
    if len(metadata_id) > 3:
        tagline = first_text(detailsPageElements.xpath('//p[contains(., "Serie")]//a[@title]'))
        metadata.title = "%s [Scene %s]" % (metadata_id[3], metadata_id[4])
    else:
        if subSite:
            tagline = siteName or (subSite if studio.replace(' ', '').lower() != subSite.replace(' ', '').lower() else None) or serieName or movieName or ''

    tagline = PAutils.parseTitle(tagline, siteNum)

    if studio:
        if studio.lower() in ['teamskeet', 'mylf']:
            subNetwork = networkReptyle.getSubNetwork(tagline)
            metadata.studio = subNetwork if subNetwork else studio
            tagline = networkReptyle.getSubSite(tagline)
        else:
            metadata.studio = studio
    else:
        metadata.studio = tagline

    if tagline and metadata.studio.replace(' ', '').lower() != tagline.replace(' ', '').lower():
        metadata.tagline = tagline

    if tagline:
        movieCollections.addCollection(tagline)
    else:
        movieCollections.addCollection(metadata.studio)

    # Release Date
    date = detailsPageElements.xpath('//span[contains(., "Release date")]')
    if date:
        date = date[0].text_content().strip()
        date = date.replace("Release date: ", "")
        date = date.replace(", more updates...\n[Nav X]", "")
        date = date.replace("* Movie Release", "")
        date = date.strip()
    else:
        date = sceneDate if sceneDate else None

    if date:
        try:
            date_object = datetime.strptime(date, "%B, %Y")
        except:
            date_object = datetime.strptime(date, "%B %d, %Y")
        metadata.originally_available_at = date_object
        metadata.year = metadata.originally_available_at.year

    # Genres
    for genreLink in detailsPageElements.xpath('//div[./b[contains(., "Categories")]]//a'):
        genreName = genreLink.text_content().strip()

        movieGenres.addGenre(genreName)

    # Actor(s)
    actors = detailsPageElements.xpath('//h3[contains(., "Cast")]//following::div[./p[contains(., "No Profile")]]//span[@class]/text()')
    actors.extend(detailsPageElements.xpath('//h3[contains(., "Cast")]//following::div//a[contains(@href, "/name/")]/img/@alt'))
    for actor in actors:
        actorName = actor
        actorPhotoURL = ''

        movieActors.addActor(actorName, actorPhotoURL)

    # Posters
    try:
        if siteNum == 1073 or siteNum == 1370:
            cover = '//a[@class="pvideof"]/@href'
            img = detailsPageElements.xpath(cover)[0]
            art.append(img)
    except:
        pass

    getData18Images(sceneURL, art, metadata, detailsPageElements=detailsPageElements)

    return metadata
