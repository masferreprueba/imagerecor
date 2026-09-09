using System.Diagnostics;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace MasFerreImageStudio;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new MainForm());
    }
}

internal sealed class MainForm : Form
{
    private const string AppUrl = "https://mas-ferre-image-studio.onrender.com";
    private readonly WebView2 browser = new() { Dock = DockStyle.Fill };
    private readonly ToolStripStatusLabel status = new("Iniciando…");

    public MainForm()
    {
        Text = "Mas Ferre · Estudio de imágenes";
        StartPosition = FormStartPosition.CenterScreen;
        MinimumSize = new Size(900, 650);
        Size = new Size(1280, 850);
        BackColor = Color.FromArgb(245, 247, 248);

        var toolbar = new ToolStrip
        {
            GripStyle = ToolStripGripStyle.Hidden,
            BackColor = Color.White,
            Padding = new Padding(8, 5, 8, 5),
            RenderMode = ToolStripRenderMode.System
        };
        var homeButton = new ToolStripButton("Inicio");
        var reloadButton = new ToolStripButton("Actualizar");
        var browserButton = new ToolStripButton("Abrir en navegador");
        homeButton.Click += (_, _) => NavigateHome();
        reloadButton.Click += (_, _) => browser.Reload();
        browserButton.Click += (_, _) => OpenInDefaultBrowser();
        toolbar.Items.Add(new ToolStripLabel("MAS FERRE") { Font = new Font("Segoe UI", 10, FontStyle.Bold) });
        toolbar.Items.Add(new ToolStripSeparator());
        toolbar.Items.Add(homeButton);
        toolbar.Items.Add(reloadButton);
        toolbar.Items.Add(browserButton);

        var statusBar = new StatusStrip();
        statusBar.Items.Add(status);

        Controls.Add(browser);
        Controls.Add(statusBar);
        Controls.Add(toolbar);
        Shown += async (_, _) => await InitializeBrowserAsync();
    }

    private async Task InitializeBrowserAsync()
    {
        try
        {
            var dataFolder = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "MasFerre",
                "ImageStudio");
            Directory.CreateDirectory(dataFolder);
            var environment = await CoreWebView2Environment.CreateAsync(userDataFolder: dataFolder);
            await browser.EnsureCoreWebView2Async(environment);
            browser.CoreWebView2.Settings.AreDevToolsEnabled = false;
            browser.CoreWebView2.Settings.IsStatusBarEnabled = false;
            browser.CoreWebView2.NavigationStarting += (_, _) => status.Text = "Cargando…";
            browser.CoreWebView2.NavigationCompleted += (_, eventArgs) =>
                status.Text = eventArgs.IsSuccess ? "Conectado" : "No fue posible cargar la herramienta";
            browser.CoreWebView2.NewWindowRequested += (_, eventArgs) =>
            {
                eventArgs.Handled = true;
                browser.CoreWebView2.Navigate(eventArgs.Uri);
            };
            NavigateHome();
        }
        catch (Exception error)
        {
            status.Text = "No se pudo iniciar la ventana integrada";
            var answer = MessageBox.Show(
                $"No fue posible iniciar Microsoft Edge WebView2.\n\n{error.Message}\n\n¿Deseas abrir la herramienta en tu navegador?",
                "Mas Ferre · Estudio de imágenes",
                MessageBoxButtons.YesNo,
                MessageBoxIcon.Warning);
            if (answer == DialogResult.Yes)
                OpenInDefaultBrowser();
        }
    }

    private void NavigateHome()
    {
        if (browser.CoreWebView2 is not null)
            browser.CoreWebView2.Navigate(AppUrl);
    }

    private static void OpenInDefaultBrowser()
    {
        Process.Start(new ProcessStartInfo(AppUrl) { UseShellExecute = true });
    }
}
