{{ define "device-properties" }}

{{/*Split into device and attribute properties*/}}
{{ $properties := dict }}
{{ $attributeProperties := dict }}
{{ range $propName, $propValue := . }}
  {{ if $propName | contains "->" }}
    {{ $attrProp := $propName | split "->" }}
    {{ $attributeProperties = merge $attributeProperties (dict $attrProp._0 (dict $attrProp._1 $propValue)) }}
  {{ else }}
    {{ $properties = merge $properties (dict $propName $propValue) }}
  {{ end }}
{{ end }}

{{/*Now create the stuctures ska-tango-util expects*/}}
properties:
  {{ range $property, $value := $properties }}
  - name: {{ $property | quote }}
    values: [{{ $value | toString | quote}}]
  {{ end }}

attribute_properties:
  {{ range $attribute, $properties := $attributeProperties }}
  - attribute: {{ $attribute | quote }}
    properties:
      {{ range $property, $value := $properties }}
      - name: {{ $property | quote }}
        values: [{{ $value | toString | quote}}]
      {{ end }}
  {{ end }}

{{ end }}
