import PAsearchSites
import PAutils


def search(results, lang, siteNum, searchData):
    words = searchData.title.lower().split(' ')
    url = PAsearchSites.getSearchBaseURL(siteNum) + '/trial/scenes/' + '-'.join(words) + '_vids.html'
    req = PAutils.HTTPRequest(url, 'HEAD')
    if req and req.ok:
        curID = PAutils.Encode(url)
        releaseDate = searchData.dateFormat() if searchData.date else ''
        results.Append(MetadataSearchResult(id='%s|%d|%s' % (curID, siteNum, releaseDate), name='%s [%s]' % (url, PAsearchSites.getSearchSiteName(siteNum)), score=100, lang=lang))

    req = PAutils.HTTPRequest(PAsearchSites.getSearchSearchURL(siteNum) + searchData.encoded)
    if req and req.ok:
        searchResults = HTML.ElementFromString(req.text)
        for searchResult in searchResults.xpath('//div[contains(@class, "search-scene-card")] | //div[@class="grid-item"]'):
            releaseDate = titleNoFormatting = ''

            href = searchResult.xpath('.//a[contains(@class, "jj-card-thumb")]/@href | .//a/@href')
            if not href:
                continue
            sceneUrl = href[0]
            curID = PAutils.Encode(sceneUrl)

            title_elements = searchResult.xpath('.//h2[contains(@class, "jj-card-title")]/text() | .//a/img/@alt | .//img/@alt')
            if title_elements:
                titleNoFormatting = PAutils.parseTitle(title_elements[0].strip(), siteNum)

            date_elements = searchResult.xpath('.//div[contains(@class, "jj-card-date")]/text()')
            if date_elements:
                date_str = date_elements[0].replace('Released:', '').strip()
                try:
                    date_obj = parse(date_str)
                    releaseDate = date_obj.strftime('%Y-%m-%d')
                except:
                    pass

            if searchData.date and releaseDate:
                score = 100 - Util.LevenshteinDistance(searchData.date, releaseDate)
            else:
                score = 100 - Util.LevenshteinDistance(searchData.title.lower(), titleNoFormatting.lower())

            results.Append(MetadataSearchResult(id='%s|%d|%s' % (curID, siteNum, releaseDate), name='%s [%s]' % (titleNoFormatting, PAsearchSites.getSearchSiteName(siteNum)), score=score, lang=lang))

    return results


def update(metadata, lang, siteNum, movieGenres, movieActors, movieCollections, art):
    metadata_id = str(metadata.id).split('|')
    sceneURL = PAutils.Decode(metadata_id[0])
    if not sceneURL.startswith('http'):
        sceneURL = PAsearchSites.getSearchBaseURL(siteNum) + sceneURL
    sceneDate = metadata_id[2]
    req = PAutils.HTTPRequest(sceneURL)
    if not req or not req.ok:
        return metadata

    detailsPageElements = HTML.ElementFromString(req.text)

    # Title
    title_elements = detailsPageElements.xpath('//h1[contains(@class, "scene-title")]/text() | //div[@class="movie_title"]/text()')
    if title_elements:
        metadata.title = PAutils.parseTitle(title_elements[0].strip(), siteNum)

    # Summary
    summary_elements = detailsPageElements.xpath('//div[contains(@class, "scene-desc")]')
    if summary_elements:
        metadata.summary = summary_elements[0].text_content().strip()
    else:
        try:
            metadata.summary = detailsPageElements.xpath('//div[@class="player-scene-description"]/span[contains(text(), "Description:")]/..')[0].text_content().replace('Description: ', '').strip()
        except:
            pass

    # Studio
    metadata.studio = PAsearchSites.getSearchSiteName(siteNum)
    movieCollections.addCollection(metadata.studio)

    # Tagline and Collection(s)
    try:
        dvdName = detailsPageElements.xpath('//div[contains(@class, "meta-item")]/div[text()="Movie"]/following-sibling::div/text() | //div[@class="player-scene-description"]//span[contains(text(), "Movie:")]/..')[0].text_content().replace('Movie:', '').replace('Feature: ', '').strip()
        metadata.tagline = dvdName
        movieCollections.addCollection(dvdName)
    except:
        pass

    # Release Date
    date_object = None
    if sceneDate:
        try:
            date_object = parse(sceneDate)
        except:
            pass

    if not date_object:
        try:
            date_str = detailsPageElements.xpath('//div[contains(@class, "meta-item")]/div[text()="Released"]/following-sibling::div/text() | //div[@class="player-scene-description"]//span[contains(text(), "Date:")]/..')[0].text_content().replace('Date: ', '').strip()
            date_object = parse(date_str)
        except:
            Log("No date found")

    if date_object:
        metadata.originally_available_at = date_object
        metadata.year = metadata.originally_available_at.year

    # Genres
    for genreLink in detailsPageElements.xpath('//div[contains(@class, "scene-cats")]/a | //span[contains(text(), "Categories")]/a'):
        genreName = genreLink.text_content().strip().lower()
        movieGenres.addGenre(genreName)

    # Actor(s)
    actors = detailsPageElements.xpath('//div[contains(@class, "scene-info")]//span[contains(@class, "update_models")]/a | //div[@class="player-scene-description"]/span[contains(text(), "Starring:")]/..//a')

    if actors:
        for actorLink in actors:
            actorName = str(actorLink.text_content().strip())
            actorPhotoURL = ''

            actorPageURL = actorLink.get('href')
            if actorPageURL:
                if 'http' not in actorPageURL:
                    actorPageURL = PAsearchSites.getSearchBaseURL(siteNum) + actorPageURL
                reqActor = PAutils.HTTPRequest(actorPageURL)
                if reqActor and reqActor.ok:
                    actorPage = HTML.ElementFromString(reqActor.text)
                    try:
                        actor_imgs = actorPage.xpath('//img[contains(@src, "contentthumbs")]/@src | //img[@class="model_bio_thumb stdimage thumbs target"]/@src0_3x')
                        if actor_imgs:
                            actorPhotoURL = actor_imgs[0]
                            if 'http' not in actorPhotoURL:
                                actorPhotoURL = PAsearchSites.getSearchBaseURL(siteNum) + actorPhotoURL
                    except:
                        pass

            movieActors.addActor(actorName, actorPhotoURL)

    # Posters / Art
    for photoImg in detailsPageElements.xpath('//a[contains(@class, "tp-photo-thumb")]/img/@src | //div[contains(@class, "tp-photos-strip")]//img/@src'):
        if 'http' not in photoImg:
            photoImg = PAsearchSites.getSearchBaseURL(siteNum) + photoImg
        art.append(photoImg)

    try:
        videoPoster = detailsPageElements.xpath('//video[@id="video-player"]/@poster')[0]
        if 'http' not in videoPoster:
            videoPoster = PAsearchSites.getSearchBaseURL(siteNum) + videoPoster
        art.append(videoPoster)
    except:
        pass

    Log('Artwork found: %d' % len(art))
    for idx, posterUrl in enumerate(art, 1):
        try:
            if not PAsearchSites.posterAlreadyExists(posterUrl, metadata):
                image = PAutils.HTTPRequest(posterUrl)
                if image and image.ok:
                    im = StringIO(image.content)
                    resized_image = Image.open(im)
                    width, height = resized_image.size
                    if width > 1 or height > width:
                        metadata.posters[posterUrl] = Proxy.Media(image.content, sort_order=idx)
                    if width > 100 and width > height:
                        metadata.art[posterUrl] = Proxy.Media(image.content, sort_order=idx)
        except:
            pass

    return metadata
