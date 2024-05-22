import streamlit as st
import subprocess
import argparse
from streamlit_agraph import agraph, Node, Edge, Config
import json
from openie import StanfordOpenIE
import spacy


properties = {
    'openie.affinity_probability_cap': 2 / 3,
}
nlp = spacy.load("en_core_web_lg")

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

def compute_similarity(triple1, triple2):
    triple_doc = nlp(triple1)   
    text_doc = nlp(triple2)
    similarity_score = triple_doc.similarity(text_doc)
    return similarity_score




parser = argparse.ArgumentParser()
parser.add_argument("--text", type=str, help="Text passed from the main app")
args = parser.parse_args()

if args.text:
    text , material = args.text.split("$plit@_-T,ext") 
    if st.sidebar.checkbox("Show Summary:"):
        st.write(text)
    if st.sidebar.checkbox("Show Knowledge Graph:"):
        triples = []
        with StanfordOpenIE(properties=properties) as client:
            demo = []
            for triple in client.annotate(text):
                demo.append(triple)
        unique_triples = []
        for triple in demo:
            is_similar = False
            for unique_triple in unique_triples:
                if triple["subject"] == unique_triple["subject"] and triple["object"] == unique_triple["object"]:
                    similarity = 1
                else:
                    similarity = compute_similarity(" ".join(triple.values()), " ".join(unique_triple.values()))
                if similarity > 0.7:
                    is_similar = True
                    break
            if not is_similar:
                unique_triples.append(triple)
        triples = []
        for triple in unique_triples:
            triples.append([triple["subject"].lower(),triple["relation"].lower(),triple["object"].lower()])
        
        config = Config(width=750,
                            height=950,
                            directed=True,
                            physics=True,
                            hierarchical=False,
                            highlightColor="#FF00FF",
                            nodeHighlightBehavior=True,     
                            node={'labelProperty':'label','renderLabel':False})
        position_show = True
        nodes , edges = create_graph(triples, position_show)
        return_value = agraph(nodes = nodes, edges = edges, config = config)
else:
    st.write("No text passed")
