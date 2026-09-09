# Mas Ferre · aplicación para Windows

Este proyecto genera una aplicación de escritorio para Windows de 64 bits. La ventana carga la versión pública de la herramienta, por lo que las mejoras publicadas en Render aparecen automáticamente sin reinstalar el programa.

## Compilar

```powershell
dotnet publish .\MasFerreImageStudio.csproj -c Release -r win-x64 --self-contained true
```

El equipo necesita conexión a internet. WebView2 viene instalado en Windows 11 y en la mayoría de los equipos con Windows 10; si no está disponible, la aplicación ofrece abrir la herramienta en el navegador predeterminado.
