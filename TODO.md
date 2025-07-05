1. Agregar visualizacion de OpenCLIP en el viewer de resultados (evaluate_validation_dataset.py)
2. Acomodar la prompt sin contexto para que se asemeje semanticamente a la prompt con contexto (Especificamente tratar de que se parezca en como pide la respuesta. Ej: "Your goal is to optimize... describe briefly... according to what the user is most likely to need)
3. For everyone: despues de generar el results viewer, mirar todos los resultados con/sin contexto (usando los cohere embeddings) y analizar lo siguiente:
    - LLM responde a la pregunta real? Si, no? Por que? 
    - Hay contenido extra? Hay contenido que falta? 
    - Que tipo de contenido extra agrego y por que crees que sucedio?
    - *Tomar en cuenta que la respuesta puede estar contaminada porque LLMs fueron entrenados en este dataset.
4. Mejorar la manera en la que visualizamos las imagenes simultaneamente (muy pequeno y solo podemos ver una a la vez)