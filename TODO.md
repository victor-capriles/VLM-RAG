1. DONE ~~Agregar visualizacion de OpenCLIP en el viewer de resultados (evaluate_validation_dataset.py)~~
2. DONE ~~AMejorar la manera en la que visualizamos las imagenes simultaneamente (muy pequeno y solo podemos ver una a la vez).~~A
3. Evaluar posibilidad de que los LLMs puedan estar respondiendo bien unicamente por el hecho de que han "visto" la data y las preguntas en VizWiz. Despues de hacer todo nuestro analisis inicial con VizWiz y derivar conclusiones, probar sistema con Eyevisor/VisionPal dataset y ver si sigue funcionando "bien". A partir de esto, ver si un modelo u otro generaliza bien a otras fotos.
4. Acomodar la prompt sin contexto para que se asemeje semanticamente a la prompt con contexto (Especificamente tratar de que se parezca en como pide la respuesta. Ej: "Your goal is to optimize... describe briefly... according to what the user is most likely to need)
5. For everyone: despues de generar el results viewer, mirar todos los resultados con/sin contexto (usando los cohere embeddings) y analizar lo siguiente:
    - LLM responde a la pregunta real? Si, no? Por que? 
    - Hay contenido extra? Hay contenido que falta? 
    - Que tipo de contenido extra agrego y por que crees que sucedio?
    - *Tomar en cuenta que la respuesta puede estar contaminada porque LLMs fueron entrenados en este dataset.
6. Arreglar inicializacion de coleccion a:
    - Que use la embedding function de Cohere (embedv4)
    - Que use Cosine Similarity (normalizar los embeddings precalculados de cohere antes de meterlos a la coleccion)
7. Relacionado con el punto anterior, tenemos que normalizar todos los embeddings precalculados de cohere (Por default son L2 distance sin normalizar) Reference: [Chroma Documentation on Embeddings and normalizing](https://docs.trychroma.com/docs/collections/configure#radix-:r6:)
    - np.linalg.norm(a) where a is your embedding
8. Document modifications to system prompt:
    - Removed knowledge cutoff
    - Removed last sentence and reincorporated to user prompt
    - Removed Your name is "Be My AI".
    - Removed "If you are not sure that your response to the question is correct, you must suggest the blind person to press the "Call a volunteer" button for guidance."