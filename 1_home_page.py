#------------------------------------------- Libraries

import streamlit as st
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from io import StringIO
from streamlit_agraph import agraph, Node, Edge, Config
from langchain_community.llms import Ollama
from neo4j import GraphDatabase
import webbrowser
import subprocess
from openai import OpenAI


#------------------------------------------- End of Libraries
#---------------------------------------------------------------------------------------
#------------------------------------------- Connection

llm = Ollama(model="llama3")

uri = "instance URI"
user = "neo4j"
password = "Enter your Neo4J instance Passoword"
driver = GraphDatabase.driver(uri, auth=(user, password))

client = OpenAI(api_key="Enter your API key")


#------------------------------------------- End of Connection
#---------------------------------------------------------------------------------------
#------------------------------------------- sesssion states

# Initialize session state variables if they don't exist
if "uploaded_files" not in st.session_state:
    st.session_state["uploaded_files"] = None

if "selected_material" not in st.session_state:
    st.session_state["selected_material"] = "Choose Material:"

if "Submit" not in st.session_state:
    st.session_state["Submit"] = False

if "selected_topic" not in st.session_state:
    st.session_state["selected_topic"] = "Choose Topic:"

if "li1" not in st.session_state:
    st.session_state["li1"] = ["Choose Topic:"]

if "previous_material" not in st.session_state:
    st.session_state["previous_material"] = "Choose Material:"

if "Show" not in st.session_state:
    st.session_state["Show"] = False

if "Neo4jDB" not in st.session_state:
    st.session_state["Neo4jDB"] = False

if "start" not in st.session_state:
    st.session_state["start"] = False

if "dic" not in st.session_state:
    st.session_state["dic"] = {}

#------------------------------------------- End of sesssion states
#---------------------------------------------------------------------------------------
#------------------------------------------- Functions

def delete_all(tx):
    tx.run("MATCH (n) DETACH DELETE n")

#_______________________________________________________________________________________

def insert_triples(tx, triples):
    for triple in triples:
        # Construct query to insert triple
        query = (
            "MERGE (subject:Entity {name: $subject}) "
            "MERGE (object:Entity {name: $object}) "
            "MERGE (subject)-[:RELATION {property: $property}]->(object)"
        )
        # Execute query
        tx.run(query, subject=triple[0], property=triple[1], object=triple[2])

#_______________________________________________________________________________________

def get_triples(tx):
    query = (
        "MATCH (subject)-[relation:RELATION]->(object) "
        "RETURN subject.name AS subject, relation.property AS property, object.name AS object"
    )
    result = tx.run(query)
    return [record for record in result]

#_______________________________________________________________________________________

@st.cache_data(show_spinner=False)
def convert_pdf_to_txt(file):
    rsrcmgr = PDFResourceManager()
    retstr = StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
    fp = file
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 0
    caching = True
    pagenos=set()

    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages, password=password,caching=caching, check_extractable=True):
        interpreter.process_page(page)

    text = retstr.getvalue()

    fp.close()
    device.close()
    retstr.close()
    return text

#_______________________________________________________________________________________

@st.cache_data(show_spinner=False)
def create_graph(listOfTriples, position_show = False):

    #creating the graph of the connection
    nodes = []
    edges = []
    execs = []

    for data in listOfTriples:
        subject = data[0]
        object = data[2]

        if subject not in execs:
            nodes.append( Node(id=subject, label=subject, symbolType = 'diamond', color="#FDD00F") )
            execs.append(subject)
            
        if object not in execs:
            nodes.append( Node(id=object, label = object, color="#07A7A6") )
            execs.append(object)
        
        relation = f"{data[1]}"

        if position_show:
            edges.append( Edge(source=subject, target=object, label=relation) )
        else:
            edges.append( Edge(source=subject, target=object) )

    return [nodes, edges]

#_______________________________________________________________________________________

@st.cache_data(show_spinner=False)
def extractTopic(course , text):
    sys_prompt = f""" 
    from the given text :{text[:int(0.5*len(text))]},that is a chapter in a course about {course}, extract entity STRICTRLY as instructed below
    1. First, look for the title.
    2. The result SHOULD NOT BE MORE THAN FOUR WORDS.
    3. The result SHOULD BE ONLY one line without any additions, like the following:
    EXAMPLE: SVM
    Example: Introduction to Linear Algebra
    4. The result SHOULD NOT be {course}.
    5. DO NOT COMMENT ON THE RESULT, ONLY RESPOND WITH THE ANSWER TO THE PROMPT.
    """  
    data = llm.invoke(sys_prompt)
    return data

#_______________________________________________________________________________________

def startApp(text,material):
    subprocess.run(["streamlit", "run", "2nd.py", "--", "--text", text+"$plit@_-T,ext"+material])

#_______________________________________________________________________________________

@st.cache_data(show_spinner=False)
def summarize_text(text):
    response = client.chat.completions.create(
                        model= "gpt-4o-2024-05-13",#"gpt-4-turbo-2024-04-09",#"gpt-4-turbo-preview",
                        messages=[
                        {
                            "role": "user",
                            "content": "Summarize content as study notes, make sure the info isnt lost"
                        },
                        {
                            "role": "user",
                            "content": text 
                        }],
                        temperature=1,
                        max_tokens=4096,
                        top_p=1,
                        frequency_penalty=0,
                        presence_penalty=0)
    return response.choices[0].message.content 

#------------------------------------------- End of Functions
#---------------------------------------------------------------------------------------
#------------------------------------------- Web Page and processing

if not st.session_state["Neo4jDB"]:
    with driver.session() as session:
        session.execute_write(delete_all)

# File uploader
uploaded_files = st.sidebar.file_uploader("Upload PDF Files:", type=['pdf'], accept_multiple_files=True)

# Material selectbox
materials = ["Choose Material:", "Introduction to Data Science", "Data Engineering", "Database", "Data Mining", "Machine Learning","Natural Language Processing" ]
selected_material = st.sidebar.selectbox("Select Material", materials)

# Update session state with the latest values
st.session_state["uploaded_files"] = uploaded_files
st.session_state["selected_material"] = selected_material

# Reset submit and selected_topic if material is changed
if st.session_state["selected_material"] != st.session_state["previous_material"]:
    st.session_state["Submit"] = False
    st.session_state["selected_topic"] = "Choose Topic:"
    st.session_state["previous_material"] = st.session_state["selected_material"]

# Show the submit button only if a file is uploaded and material is selected
if st.session_state["uploaded_files"] and st.session_state["selected_material"] != "Choose Material:":
    if st.sidebar.button("Submit"):
        st.session_state["Submit"] = True


# Display second selectbox if Submit is clicked
if st.session_state["Submit"]:
    #dic = {}
    #content = []
    li0 = []

    if not st.session_state["start"]:
        st.session_state["li1"] = ["Choose Topic:"]
        st.session_state["start"] = True

    for file in st.session_state["uploaded_files"]:

        text = convert_pdf_to_txt(file)
        
        #st.write(text)
        #----------------------------------------- Text Pre-Processing and Summarization Part
        
        with driver.session() as session:
            result = session.execute_write(get_triples)
        
        for record in result:
            li0.append([record["subject"],record["property"],record["object"]])
            
        summarized_text = summarize_text(text)
        

        #----------------------------------------- End of Text Pre-Processing and Summarization Part
        #-------------------------------------------------------------------------------------------
        #----------------------------------------- Triples Part
        
        topic = extractTopic(course=st.session_state["selected_material"], text=summarized_text)
        li0.append([st.session_state["selected_material"],"is a course in ","Data Science Department"])
        li0.append([topic,"is a chapter in",st.session_state["selected_material"]])

        if topic not in st.session_state["li1"]:
            st.session_state["li1"].append(topic)
            st.session_state["dic"][topic] = summarized_text

        #----------------------------------------- End of Triples Part
        #-------------------------------------------------------------------------------------------
        #----------------------------------------- Graph Construction

        config = Config(width=750,
                            height=950,
                            directed=True,
                            physics=True,
                            hierarchical=False,
                            highlightColor="#FF00FF",
                            nodeHighlightBehavior=True,
                            node={'labelProperty':'label','renderLabel':False})
            
        position_show = True
            
        nodes , edges = create_graph(li0, position_show)

    st.session_state["Neo4jDB"] = True
    
    with driver.session() as session:
        session.execute_write(insert_triples, li0) 

    return_value = agraph(nodes = nodes, edges = edges, config = config)

        #----------------------------------------- Graph Construction
        #-------------------------------------------------------------------------------------------
            
    st.sidebar.title("Check content!")
    selected_topic = st.sidebar.selectbox("Options:", st.session_state["li1"], key="selected_topic_selectbox")

    if selected_topic != "Choose Topic:":
        st.session_state["selected_topic"] = selected_topic
        
        if st.sidebar.button("Show"):
            startApp(st.session_state["dic"][selected_topic],st.session_state["selected_material"])
            #st.sidebar.write(st.session_state["dic"][selected_topic])
            st.session_state["Show"] = not st.session_state["Show"]
    else:
        st.session_state["selected_topic"] = "None"

st.sidebar.write("You selected material:", st.session_state["selected_material"])
st.sidebar.write("Submit status:", st.session_state["Submit"])
st.sidebar.write("Selected topic:", st.session_state["selected_topic"])

#------------------------------------------- End of Web Page and processing