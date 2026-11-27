#!/bin/bash

echo "Setting up DB..."

INIT_GRAPH_CYPHER=$(cat <<-END
CALL n10s.graphconfig.init({
  handleVocabUris: 'MAP', 
  handleMultival: 'OVERWRITE', 
  keepLangTag: false, 
  keepCustomDataTypes: true, 
  applyNeo4jNaming: true 
})
END
)

CREATE_UNIQUE_CONSTRAINT="CREATE CONSTRAINT n10s_unique_uri FOR (r:Resource) REQUIRE r.uri IS UNIQUE"

RDF_FILES=$(ls /rdf-data/*.ttl)

cypher-shell --non-interactive -a "neo4j://adbs-neo4j:7687" -u neo4j -p neo4jneo4j "$INIT_GRAPH_CYPHER"

cypher-shell --non-interactive -a "neo4j://adbs-neo4j:7687" -u neo4j -p neo4jneo4j "$CREATE_UNIQUE_CONSTRAINT"

for file in $RDF_FILES; do
	echo "Inserting RDF data from $file"
	cypher-shell --non-interactive -a "neo4j://adbs-neo4j:7687" -u neo4j -p neo4jneo4j "CALL n10s.rdf.import.fetch(\"file://$file\",\"Turtle\");"
done

echo "DB setup completed"
