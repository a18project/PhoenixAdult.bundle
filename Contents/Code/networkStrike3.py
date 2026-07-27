import PAsearchSites
import PAutils


def getDatafromAPI(url, query, variables, referer):
    headers = {
        'Content-Type': 'application/json',
        'Referer': referer
    }
    params = json.dumps({'query': query, 'variables': json.loads(variables)})
    req = PAutils.HTTPRequest(url, params=params, headers=headers)

    if req and req.ok:
        try:
            return req.json()['data']
        except Exception:
            pass

    return None


def search(results, lang, siteNum, searchData):
    sceneID = None
    parts = searchData.title.split()
    first_part = parts[0] if parts else ''

    is_digit = False
    try:
        is_digit = first_part.isdigit()
    except Exception:
        pass

    if is_digit and len(first_part) > 4:
        sceneID = first_part
        searchData.title = searchData.title.replace(sceneID, '', 1).strip()

        search_variables = json.dumps({'videoId': sceneID, 'site': PAsearchSites.getSearchSiteName(siteNum).upper()})
        searchResult = getDatafromAPI(PAsearchSites.getSearchSearchURL(siteNum), search_id_query, search_variables, PAsearchSites.getSearchBaseURL(siteNum))
        if searchResult and 'findOneVideo' in searchResult and searchResult['findOneVideo']:
            video = searchResult['findOneVideo']
            titleNoFormatting = PAutils.parseTitle(video['title'], siteNum)
            releaseDate = parse(video['releaseDate']).strftime('%Y-%m-%d')
            curID = PAutils.Encode(video['slug'])
            videoID = str(video['videoId'])

            if str(sceneID) == videoID:
                score = 100
            elif searchData.date:
                score = 100 - Util.LevenshteinDistance(searchData.date, releaseDate)
            else:
                score = 100 - Util.LevenshteinDistance(searchData.title.lower(), titleNoFormatting.lower())

            results.Append(MetadataSearchResult(id='%s|%d' % (curID, siteNum), name='%s %s' % (titleNoFormatting, releaseDate), score=score, lang=lang))
    else:
        search_variables = json.dumps({'query': searchData.title, 'site': PAsearchSites.getSearchSiteName(siteNum).upper(), 'first': 10, 'skip': 0})
        searchResults = getDatafromAPI(PAsearchSites.getSearchSearchURL(siteNum), search_query, search_variables, PAsearchSites.getSearchBaseURL(siteNum))
        if searchResults and 'searchVideos' in searchResults and searchResults['searchVideos']:
            for searchResult in searchResults['searchVideos']['edges']:
                node = searchResult['node']
                titleNoFormatting = PAutils.parseTitle(node['title'], siteNum)
                releaseDate = parse(node['releaseDate']).strftime('%Y-%m-%d')
                curID = PAutils.Encode(node['slug'])

                if searchData.date:
                    score = 100 - Util.LevenshteinDistance(searchData.date, releaseDate)
                else:
                    score = 100 - Util.LevenshteinDistance(searchData.title.lower(), titleNoFormatting.lower())

                results.Append(MetadataSearchResult(id='%s|%d' % (curID, siteNum), name='%s %s' % (titleNoFormatting, releaseDate), score=score, lang=lang))

    return results


def update(metadata, lang, siteNum, movieGenres, movieActors, movieCollections, art):
    metadata_id = str(metadata.id).split('|')
    sceneName = PAutils.Decode(metadata_id[0])

    update_variables = json.dumps({'slug': sceneName, 'site': PAsearchSites.getSearchSiteName(siteNum).upper()})
    detailsPageElements = getDatafromAPI(PAsearchSites.getSearchSearchURL(siteNum), update_query, update_variables, PAsearchSites.getSearchBaseURL(siteNum))
    if not detailsPageElements or 'findOneVideo' not in detailsPageElements or not detailsPageElements['findOneVideo']:
        return metadata

    video = detailsPageElements['findOneVideo']
    pictureset = video.get('carousel', [])

    # Title
    metadata.title = PAutils.parseTitle(video['title'], siteNum)

    # Summary
    metadata.summary = video.get('description', '')

    # Studio
    metadata.studio = PAsearchSites.getSearchSiteName(siteNum).title()

    # Tagline and Collection(s)
    movieCollections.addCollection(metadata.studio)

    # Release Date
    if 'releaseDate' in video and video['releaseDate']:
        date_object = parse(video['releaseDate'])
        metadata.originally_available_at = date_object
        metadata.year = metadata.originally_available_at.year

    # Genres
    if metadata.studio in ['Tushy', 'Tushyraw', 'TushyRaw']:
        movieGenres.addGenre('Anal')

    if video.get('categories'):
        for tag in video['categories']:
            genreName = tag['name']
            movieGenres.addGenre(genreName)

    # Actor(s)
    actors = video.get('models', [])
    for actor in actors:
        actorName = actor['name']
        actorPhotoURL = ''
        if actor.get('images') and actor['images'].get('listing'):
            try:
                actorPhotoURL = actor['images']['listing'][0]['highdpi']['double']
            except (KeyError, IndexError):
                pass

        movieActors.addActor(actorName, actorPhotoURL)

    # Director
    if video.get('directors'):
        directorName = video['directors'][0]['name']
        movieActors.addDirector(directorName, '')

    # Posters
    if video.get('images'):
        for name in ['movie', 'poster']:
            if name in video['images'] and video['images'][name]:
                try:
                    image = video['images'][name][-1]
                    if 'highdpi' in image:
                        art.append(image['highdpi']['3x'])
                    else:
                        art.append(image['src'])
                    break
                except (KeyError, IndexError):
                    pass

    if pictureset:
        for image in pictureset:
            try:
                img = image['listing'][0]['highdpi']['triple']
                art.append(img)
            except (KeyError, IndexError):
                pass

    images = []
    posterExists = False
    Log('Artwork found: %d' % len(art))
    for idx, posterUrl in enumerate(art, 1):
        cleanUrl = posterUrl.split('?')[0]
        art[idx - 1] = cleanUrl
        if not PAsearchSites.posterAlreadyExists(cleanUrl, metadata):
            try:
                image = PAutils.HTTPRequest(posterUrl)
                if image and image.ok:
                    im = StringIO(image.content)
                    resized_image = Image.open(im)
                    width, height = resized_image.size
                    if height > width:
                        metadata.posters[cleanUrl] = Proxy.Media(image.content, sort_order=idx)
                        posterExists = True
                    if width > height:
                        images.append((image, cleanUrl))
                        metadata.art[cleanUrl] = Proxy.Media(image.content, sort_order=idx)
            except:
                pass
        elif PAsearchSites.posterOnlyAlreadyExists(cleanUrl, metadata):
            posterExists = True

    if not posterExists:
        for idx, (image, cleanUrl) in enumerate(images, 1):
            try:
                im = StringIO(image.content)
                resized_image = Image.open(im)
                width, height = resized_image.size
                if width > 1:
                    metadata.posters[cleanUrl] = Proxy.Media(image.content, sort_order=idx)
            except:
                pass

    return metadata


search_query = 'query getSearchResults($query: String!, $site: Site!, $first: Int, $skip: Int) { searchVideos(input: {query: $query, site: $site, first: $first, skip: $skip}) { edges { node { videoId title releaseDate slug images { listing { src } } } } } }'
update_query = 'query getSearchResults($slug: String!, $site: Site!) { findOneVideo(input: {slug: $slug, site: $site}) { videoId title description releaseDate models { name slug images { listing { highdpi { double } } } } directors { name } categories { name } carousel { listing { highdpi { triple } } } } }'
search_id_query = 'query getSearchResults($videoId: ID!, $site: Site!) { findOneVideo(input: {videoId: $videoId, site: $site}) { videoId title releaseDate slug } }'
