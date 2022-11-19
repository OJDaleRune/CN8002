#import libraries
import collections
from pyzotero import zotero
from soupsieve import match
import Configuration
from datetime import datetime
import re
import bibtexparser
import html2text
import json

#Script Settings
library_id = Configuration.library_id
api_key = Configuration.api_key
library_type = Configuration.library_type
parent_collection = Configuration.parent_collection
subcollection = Configuration.subcollection

#Create file
timestamp = datetime.now()
timestamp = timestamp.strftime("%d%m%Y_%H%M%S")
references_file_name = "ReferenceList-" + timestamp + "-working.cypher"
file = open(references_file_name, "x", encoding="UTF-8")
#Add unique node constraints
file.write("CREATE CONSTRAINT ON (year:Year) ASSERT year.year IS UNIQUE;\n")
file.write("CREATE CONSTRAINT ON (researcher:Researcher) ASSERT researcher.name IS UNIQUE;\n")
file.write("CREATE CONSTRAINT ON (journal:Journal) ASSERT journal.name IS UNIQUE;\n")
file.write("CREATE CONSTRAINT ON (topic:Topic) ASSERT topic.topic IS UNIQUE;\n")
file.write("CREATE CONSTRAINT ON (future_work_suggestion:Future_Work_Suggestion) ASSERT future_work_suggestion.suggestion IS UNIQUE;\n")

#Get the right papers out of Zotero
zot = zotero.Zotero(library_id, library_type, api_key)
collections = zot.collections()
for collection in collections:
    if (collection['data']['name'] == parent_collection):
        parent_key = collection['data']['key']
for collection in collections:
    if (parent_key == collection['data']['parentCollection'] and collection['data']['name'] == subcollection):
        subcollection_key = collection['data']['key']

#Populate the cypher commands
items = zot.collection_items(subcollection_key)
for item in items:
    if item['data']['itemType'] == "journalArticle":
        item_key = item['key']
                
        #Compose Year statement with regex:
        year = re.findall("\d\d\d\d", item['data']['date'])
        year_string = "year_" + str(year[0])
        year = year[0]
        year_node = "MERGE (" + year_string + ": Year{year: " + year + "});"
        file.write(str(year_node) + "\n")

        children = zot.children(item_key, itemType='note')
        for child in children:
            plaintext_note = html2text.html2text(child['data']['note'])
            note_type = plaintext_note.splitlines()[0]
            if "Cited By :" in note_type:
                cited_by = note_type.split(":")[1]
        
        #Compose statement to extract paper title:
        title = (item['data']['title'])
        title_node = "MERGE (`" + title + "`: `Survey Paper`{title: \"" + title + "\", citations: " + cited_by + "});" 
        file.write(str(title_node) + "\n")

        #Relate paper to year:
        published_in = "MATCH (`" + title + "`: `Survey Paper`{title: \"" + title + "\"}) MATCH (" + year_string + ": Year{year: " + year + "}) MERGE (`" + title + "`) -[:PUBLISHED_IN]->(" + year_string + ");" 
        file.write(str(published_in) + "\n")

        #Compose journal statements:
        journal = item['data']['publicationTitle']
        journal_node = "MERGE (`" + journal + "`: Journal{name: \"" + journal + "\"});" 
        file.write(str(journal_node) + "\n")

        #Relate journal to papers:
        published_by = "MATCH (`" + title + "`: `Survey Paper`{title: \"" + title + "\"}) MATCH (`" + journal + "`: Journal{name: \"" + journal + "\"}) MERGE (`" + title + "`) -[:PUBLISHED_BY]->(`" + journal + "`);" 
        file.write(str(published_by) + "\n")

        #Compose researcher statements:
        researchers = item['data']['creators']
        for researcher in researchers:
            full_name = researcher['lastName'] + ", " + researcher['firstName'][0] + "."
            researcher_node = "MERGE (`" + full_name + "`: Researcher{name: \"" + full_name + "\"});"
            file.write(str(researcher_node) + "\n")

            #Relate researcher(s) to paper:
            contributed_to = "MATCH (`" + full_name + "`: Researcher{name: \"" + full_name + "\"}) MATCH (`" + title + "`: `Survey Paper`{title: \"" + title + "\"}) MERGE (`" + full_name + "`) -[:CONTRIBUTED_TO]->(`" + title + "`);" 
            file.write(str(contributed_to) + "\n")

        #Compose statements to extract topics:
        tags = item['data']['tags']
        for tag in tags:
            tag_content = tag['tag']
            tag_node =  "MERGE (`" + tag_content + "`: topic{topic: \"" + tag_content + "\"});"
            file.write(str(tag_node) + "\n")
            #relate topic to paper:
            investigates = "MATCH (`" + tag_content + "`: topic{topic: \"" + tag_content + "\"}) MATCH (`" + title + "`: `Survey Paper`{title: \"" + title + "\"}) MERGE (`" + tag_content + "`) -[:INVESTIGATES]->(`" + title + "`);" 
            file.write(str(investigates) + "\n") 

        #relate topic/key words to paper:

        for child in children:
            plaintext_note = html2text.html2text(child['data']['note'])
            note_type = plaintext_note.splitlines()[0]
            if note_type == "Future Work Recommendations |":
                future_works = plaintext_note.splitlines()
                #tidy up the list:
                del future_works[0]
                future_works = list(filter(None, future_works))
                for work in future_works:
                    #compose future work ideas:
                    future_work_node = "MERGE (`" + work + "`: `Future Work`{`future work`: \"" + work + "\"});"
                    file.write(str(future_work_node) + "\n")

                    #relate survey paper to future work ideas:
                    future_work = "MATCH (`" + work + "`: `Future Work`{`future work`: \"" + work + "\"}) MATCH (`" + title + "`: `Survey Paper`{title: \"" + title + "\"}) MERGE (`" + title + "`) -[:SUGGESTS]->(`" + work + "`);" 
                    file.write(str(future_work) + "\n")                    

            if note_type == "References |":
                bib_database = bibtexparser.loads(plaintext_note)
                for entry in bib_database.entries:
                    #Create statement to get a list of references from the survey paper:   
                    #compose title statements including citation count (notes)
                    try:
                        ref_title = entry['title']
                        ref_title = ref_title.replace("\n", "")
                        ref_title = ref_title = ref_title.replace('"', r'\"')
                        ref_cite_count = entry['note']
                        ref_cite_count = ref_cite_count.split(" ")
                        ref_cite_count = ref_cite_count[2]
                        title_node = "MERGE (`" + ref_title + "`: `Referenced Paper`{title: \"" + ref_title + "\", citations: " + ref_cite_count + "});" 
                        file.write(str(title_node) + "\n")
                    except:
                        continue

                    #Compose Year statements
                    ref_year = entry['year']
                    ref_year_string = "Year_" + str(ref_year)
                    ref_year_node = "MERGE (" + ref_year_string + ": Year{year: " + ref_year + "});"
                    file.write(str(ref_year_node) + "\n")

                    #relate paper to year
                    ref_published_in = "MATCH (`" + ref_title + "`: `Referenced Paper`{title: \"" + ref_title + "\"}) MATCH (" + ref_year_string + ": Year{year: " + ref_year + "}) MERGE (`" + ref_title + "`) -[:PUBLISHED_IN]->(" + ref_year_string + ");" 
                    file.write(str(ref_published_in) + "\n")

                    #Compose jounral statements
                    try:
                        ref_journal = entry['journal']
                        ref_journal = ref_journal.replace("\n", "")
                    except:
                        ref_journal = "Not Listed"                    
                    ref_journal_node = "MERGE (`" + ref_journal + "`: Journal{name: \"" + ref_journal + "\"});" 
                    file.write(str(journal_node) + "\n")

                    #relate paper to journal
                    ref_published_by = "MATCH (`" + ref_title + "`: `Referenced Paper`{title: \"" + ref_title + "\"}) MATCH (`" + ref_journal + "`: Journal{name: \"" + ref_journal + "\"}) MERGE (`" + ref_title + "`) -[:PUBLISHED_BY]->(`" + ref_journal + "`);" 
                    file.write(str(ref_published_by) + "\n")

                    #compose author statements
                    ref_researchers = entry['author']
                    ref_researchers = ref_researchers.split(" and")
                    for researcher in ref_researchers:
                        researcher = researcher.replace("\n", "")
                        ref_researcher_node = "MERGE (`" + researcher + "`: Researcher{name: \"" + researcher + "\"});"
                        file.write(str(ref_researcher_node) + "\n")

                        #Relate researcher(s) to paper:
                        ref_contributed_to = "MATCH (`" + researcher + "`: Researcher{name: \"" + researcher + "\"}) MATCH (`" + ref_title + "`: `Referenced Paper`{title: \"" + ref_title + "\"}) MERGE (`" + researcher + "`) -[:CONTRIBUTED_TO]->(`" + ref_title + "`);" 
                        file.write(str(ref_contributed_to) + "\n")

                    #link survey paper to references
                    references = "MATCH (`" + title + "`: `Survey Paper`{title: \"" + title + "\"}) MATCH (`" + ref_title + "`: `Referenced Paper`{title: \"" + ref_title + "\"}) MERGE (`" + title + "`) -[:REFERENCES]->(`" + ref_title + "`);" 
                    file.write(str(references) + "\n")

#Close file
file.close()
file = open(references_file_name, "r", encoding="UTF-8")

#Tidy up cypher script
contents = file.read()
contents = contents.splitlines()
contents_unique=[]
for line in contents:
        if line not in contents_unique:
            contents_unique.append(line)

references_file_name_unique = "ReferenceList-" + timestamp + ".cypher"
file_unique = open(references_file_name_unique, "x", encoding="UTF-8")
with file_unique as fp:
    for item in contents_unique:
        fp.write("%s\n" % item)

