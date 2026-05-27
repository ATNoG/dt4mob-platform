package templates

import (
	_ "embed"
	"fmt"
	"text/template"
)

//go:embed hono_connection.tpl
var HonoConnectionTemplate string

//go:embed export_connection.tpl
var ExportConnectionTemplate string

//go:embed system_service_policy.json
var SystemServicePolicy string

func CreateTemplate(name string, rawTemplate string) (*template.Template, error) {
	return template.New(name).Funcs(template.FuncMap{
		"quote": func(val string) string {
			return fmt.Sprintf("\"%s\"", val)
		},
	}).Parse(rawTemplate)
}
