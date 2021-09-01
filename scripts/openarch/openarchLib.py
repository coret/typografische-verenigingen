#! /usr/bin/env python3
# Python3 library for operations on openarch.nl using the openarch API
# see: https://api.openarch.nl/

import requests
import json
import rdflib
import unidecode

from rdflib.namespace import XSD

from time import sleep

#######
# searchDoc
# function to find list of events querying on personName, period (before, after) and relationType
def searchDoc(personName, before, after, relationType):

    # API variables
    baseUrl = "https://api.openarch.nl/1.0/records/search.json?"
    lang = "nl"
    numberShow = 25

    # initialize variables for loop
    page = 0
    numberFound = 0
    result = []
    while (numberFound >= (page * numberShow)):
        start = page * numberShow
        reqUrl = baseUrl + \
                "name=" + personName + \
                "+" + str(after) + "-" + str(before) + \
                "&relationtype=" + relationType + \
                "&lang=" + lang + \
                "&number_show=" + str(numberShow) + \
                "&start=" + str(start)

        r = requests.get(reqUrl)
        print(reqUrl) # for debugging
        sleep(0.25) # prevent server overload
        jsonResultList = json.loads(r.text)

        numberFound = int(jsonResultList['response']['number_found'])
        end = numberFound - start
        if end > numberShow:
            end = numberShow

        for i in range(0,end):
            url = jsonResultList['response']['docs'][i]['url']
            result.append(url)

        page = page + 1

    return result


#######
# showDoc
# function to get A2A json
def showDoc(url):

    baseUrl = "https://api.openarch.nl/1.0/records/show.json?"

    # if url is the human-readable landingpage, construct REST-url
    url = url.strip() # remove trailing spaces
    if (url.find("show.php") > 0): 
        reqUrl = url.replace("https://www.openarch.nl/show.php?", baseUrl)
    else:
        pid = url.replace("https://www.openarch.nl/","")
        arch_guid = pid.split(":")
        reqUrl = baseUrl + \
                "archive=" + arch_guid[0] + \
                "&identifier=" + arch_guid[1]

    # error handling
    if (reqUrl != ""):
        # do request
        r = requests.get(reqUrl)
        print(reqUrl) # for debugging and progress
        sleep(0.25) # prevent server overload
        if r.text:
            jsonResult = json.loads(r.text)
        else:
            jsonResult = {}
            jsonResult['error_description'] = "empty result"
    else:
        jsonResult = {}
        jsonResult['error_description'] = "empty url"

    # jsonResult should be a list of items
    # if jsonResult is of type 'dict', then jsonResult is an errormessage
    if type(jsonResult) is dict:
        error = jsonResult
        jsonResult = {}
        jsonResult['error_description'] = error

    return jsonResult

# function to create a dict, created from A2A json
def createDict(jsonResult):

    row = {}
    row['url']    = url

    # handle Event-part of the A2A record
    a2aEvent       = jsonResult[0].get('a2a_Event', {})

    # get plaats
    a2aEventPlace  = a2aEvent.get('a2a_EventPlace', {})
    a2aPlace       = a2aEventPlace.get('a2a_Place', {})
    row['plaats']  = a2aPlace.get('a2a_Place', "")

    # get gebeurtenis
    a2aEventType       = a2aEvent.get('a2a_EventType', {})
    row['gebeurtenis'] = a2aEventType.get('a2a_EventType', "")

    # get jaar/maand/dag
    a2aEventDate = a2aEvent.get('a2a_EventDate', {})
    a2aYear      = a2aEventDate.get('a2a_Year', {})
    row['jaar']  = a2aYear.get('a2a_Year', "")
    a2aMonth     = a2aEventDate.get('a2a_Month', {})
    row['maand'] = a2aMonth.get('a2a_Month', "")
    a2aDay       = a2aEventDate.get('a2a_Day', {})
    row['dag']   = a2aDay.get('a2a_Day', "")

    # rollen
    roles = {}
    for r in jsonResult[0]['a2a_RelationEP']:
        keyref = r['a2a_PersonKeyRef']['a2a_PersonKeyRef']
        role   = r['a2a_RelationType']['a2a_RelationType']
        roles[keyref] = role.replace(" ","_")

    # persoonsnamen
    for p in jsonResult[0]['a2a_Person']:

        a2aPersonName = p.get('a2a_PersonName', {})

        keyref = p['pid']
        role = roles[keyref]

        key = "voornaam" + role
        a2aPersonNameFirstName = a2aPersonName.get('a2a_PersonNameFirstName', {})
        row[key] =  a2aPersonNameFirstName.get('a2a_PersonNameFirstName', "")

        key = "tussenvoegsel" + role
        a2aPersonNamePrefixLastName = a2aPersonName.get('a2a_PersonNamePrefixLastName', {})
        row[key] =  a2aPersonNamePrefixLastName.get('a2a_PersonNamePrefixLastName', "")

        key = "achternaam" + role
        a2aPersonNameLastName = a2aPersonName.get('a2a_PersonNameLastName', {})
        row[key] =  a2aPersonNameLastName.get('a2a_PersonNameLastName', "")

    return row

#####
def charReplace(string):

    string = string.lower()

    string = string.replace("ch","g")
    string = string.replace("c","k")
    string = string.replace("z","s")
    string = string.replace("ph","f")
    string = string.replace("ij","y")

    string = unidecode.unidecode(string)

    return string

#####
# creates RDF complying to the schema-definition of CLARIAH/burgerLinker
def createGraph(jsonResult, url):

    rdf     = rdflib.Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    civ     = rdflib.Namespace("https://iisg.amsterdam/id/civ/")
    schema  = rdflib.Namespace("http://schema.org/")

    g = rdflib.Graph()
    g.namespace_manager.bind('civ', civ, override=False)
    g.namespace_manager.bind('schema', schema, override=False)

    akteIRI = rdflib.URIRef(url)

    ### civ:Event ###
    # handle Event-part of the A2A record
    a2aEvent        = jsonResult[0].get('a2a_Event', {})

    # gebeurtenis
    a2aEventType    = a2aEvent.get('a2a_EventType', {})
    gebeurtenis     = a2aEventType.get('a2a_EventType', "")

    eventIRI = rdflib.URIRef(url + "#" + gebeurtenis)

    if (gebeurtenis == "Geboorte"):
        typeIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/Birth")
    elif (gebeurtenis == "Overlijden"):
        typeIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/Death")
    elif (gebeurtenis == "Huwelijk"):
        typeIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/Marriage")
    else:
        typeIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/Event")
    g.add((eventIRI,rdf.type,typeIRI))

    # plaats
    a2aEventPlace  = a2aEvent.get('a2a_EventPlace', {})
    a2aPlace       = a2aEventPlace.get('a2a_Place', {})
    plaats         = a2aPlace.get('a2a_Place', "")

    g.add((eventIRI,civ.eventLocation,rdflib.Literal(plaats)))

    registrationID = url.replace("https://www.openarch.nl/","")
    g.add((eventIRI,civ.registrationID,rdflib.Literal(registrationID.replace(":","_"))))
    
    # datum
    a2aEventDate = a2aEvent.get('a2a_EventDate', {})
    a2aYear      = a2aEventDate.get('a2a_Year', {})
    jaar         = a2aYear.get('a2a_Year', "")
    a2aMonth     = a2aEventDate.get('a2a_Month', {})
    maand        = a2aMonth.get('a2a_Month', "")
    maand        = str(maand).zfill(2)
    a2aDay       = a2aEventDate.get('a2a_Day', {})
    dag          = a2aDay.get('a2a_Day', "")
    dag          = str(dag).zfill(2)

    datum        = jaar + "-" + maand + "-" + dag

    g.add((eventIRI,civ.eventDate,rdflib.Literal(datum, datatype=XSD.date)))

    ### civ:Person

    # rollen
    lyst = []
    if type(jsonResult[0]['a2a_RelationEP']) is list: 
        lyst = jsonResult[0]['a2a_RelationEP']
    else:
        lyst.append(jsonResult[0]['a2a_RelationEP'])

    roles = {}
    for r in lyst:
        keyref = r['a2a_PersonKeyRef']['a2a_PersonKeyRef']
        role   = r['a2a_RelationType']['a2a_RelationType']
        roles[keyref] = role.replace(" ","_")

    # persoonsnamen
    lyst = []
    if type(jsonResult[0]['a2a_Person']) is list: 
        lyst = jsonResult[0]['a2a_Person']
    else:
        lyst.append(jsonResult[0]['a2a_Person'])

    for p in lyst:
        a2aPersonName = p.get('a2a_PersonName', {})
        personPid = p['pid']

        personIRI = rdflib.URIRef(url + "#" + personPid)
        typeIRI = rdflib.URIRef("http://schema.org/Person")
        g.add((personIRI,rdf.type,typeIRI))
        g.add((personIRI,civ.personID,rdflib.Literal(personPid.replace(":","_"))))

        a2aPersonNameFirstName = a2aPersonName.get('a2a_PersonNameFirstName', {})
        givenName =  a2aPersonNameFirstName.get('a2a_PersonNameFirstName', "")
        g.add((personIRI,schema.givenName,rdflib.Literal(charReplace(givenName))))

        a2aPersonNamePrefixLastName = a2aPersonName.get('a2a_PersonNamePrefixLastName', {})
        infix =  a2aPersonNamePrefixLastName.get('a2a_PersonNamePrefixLastName', "")
        if (infix != ""):
            g.add((personIRI,civ.prefixFamilyName,rdflib.Literal(charReplace(infix))))

        a2aPersonNameLastName = a2aPersonName.get('a2a_PersonNameLastName', {})
        lastName =  a2aPersonNameLastName.get('a2a_PersonNameLastName', "")
        g.add((personIRI, schema.familyName,rdflib.Literal(charReplace(lastName))))

        # relating Event to Person with role-properties
        if personPid in roles: 
            rol = roles[personPid]

            if (rol == "Moeder"):
                roleIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/mother")
                genderDerived = "f"
            elif (rol == "Vader"):
                roleIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/father")
                genderDerived = "m"
            elif (rol == "Kind"):
                roleIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/newborn")
                genderDerived = "?"
            elif (rol == "Partner"):
                roleIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/partner")
                genderDerived = "?"
            elif (rol == "Overledene"):
                roleIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/deceased")
                genderDerived = "?"
            elif (rol == "Bruid"):
                roleIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/bride")
                genderDerived = "f"
            elif (rol == "Bruidegom"):
                roleIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/groom")
                genderDerived = "m"
            elif (rol == "Vader_van_de_bruid"):
                roleIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/fatherBride")
                genderDerived = "m"
            elif (rol == "Moeder_van_de_bruid"):
                roleIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/motherBride")
                genderDerived = "f"
            elif (rol == "Vader_van_de_bruidegom"):
                roleIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/fatherGroom")
                genderDerived = "m"
            elif (rol == "Moeder_van_de_bruidegom"):
                roleIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/motherGroom")
                genderDerived = "f"
            else:
                roleIRI = rdflib.URIRef("https://iisg.amsterdam/id/civ/participant")
                genderDerived = "?"

            g.add((eventIRI,roleIRI,personIRI))

        # gender
        a2aGender = p.get('a2a_Gender', {})
        genderFromData = a2aGender.get('a2a_Gender', {})

        if (genderFromData == "Man"):
            gender = "m"
        elif (genderFromData == "Vrouw"):
            gender = "f"
        else:
            gender = genderDerived

        if (gender != '?'):
            g.add((personIRI, schema.gender,rdflib.Literal(gender)))

        # occupation
        a2aGender = p.get('a2a_Profession', {})
        occupation = a2aGender.get('a2a_Profession', {})
        if (len(occupation) > 0):
            g.add((personIRI, schema.hasOccupation, rdflib.Literal(occupation)))

    return g
