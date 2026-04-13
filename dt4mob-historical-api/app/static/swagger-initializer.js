window.onload = function() {
    console.log("Initializing Swagger...");
    
    const ui = SwaggerUIBundle({
        url: "/historic/openapi.json",
        dom_id: '#swagger-ui',
        presets: [
            SwaggerUIBundle.presets.apis,
            SwaggerUIBundle.SwaggerUIStandalonePreset
        ],
        layout: "BaseLayout"
    });

    window.ui = ui;
};