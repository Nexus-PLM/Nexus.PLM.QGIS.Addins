using System.Text;
using Nexus.PLM.Addin.Sdk.Translators;
using Xunit;

namespace Nexus.PLM.QGIS.Translators.Tests;

/// <summary>
/// Runs the manifest entries for real, exactly as the Translation server's script runner
/// does (launcher as the process, placeholders expanded, env from the entry). Two fixtures:
/// the repo's sample project (a saved print layout, no layers, a space in its name) and
/// <c>fixtures/plots.qgz</c> (three polygons from the GeoJSON beside it, no layout). Needs
/// QGIS: skipped unless <c>QGIS_PYTHON_CMD</c> points at <c>python-qgis.bat</c>, so CI's
/// Linux runner stays green and a developer with QGIS 4 installed gets the proof. Measured on
/// QGIS 4.2.2, 10 Oct 2026: about five seconds per export.
/// </summary>
public class QgisExportEndToEndTests
{
    private static readonly string? QgisPython = Environment.GetEnvironmentVariable("QGIS_PYTHON_CMD");

    private static readonly string PluginDir = Path.Combine(AppContext.BaseDirectory, "translators");

    private static readonly string SampleProject = Path.Combine(AppContext.BaseDirectory, "fixtures", "QGIS Project.qgz");

    private static readonly string PlotsProject = Path.Combine(AppContext.BaseDirectory, "fixtures", "plots.qgz");

    /// <summary>Every entry, run through the launcher, yields a file of its format: the PDF
    /// from a saved layout and from the no-layout fallback page, the PNG and GeoPackage from
    /// the project with layers.</summary>
    [Theory]
    [InlineData("qgis_to_pdf", "sample", "%PDF")]
    [InlineData("qgis_to_pdf", "plots", "%PDF")]
    [InlineData("qgis_to_png", "plots", "\u0089PNG")]
    [InlineData("qgis_to_gpkg", "plots", "SQLite format 3")]
    public async Task EachEntryExportsAProject(string key, string fixture, string magic)
    {
        if (!QgisAvailable()) return;

        var bytes = await RunEntry(key, fixture == "sample" ? SampleProject : PlotsProject);

        Assert.True(bytes.Length > 500, $"{key} produced {bytes.Length} bytes");
        Assert.Equal(magic, Encoding.Latin1.GetString(bytes, 0, magic.Length));
    }

    /// <summary>
    /// The sample project carries a print layout and no layers, so GeoPackage export has
    /// nothing to package: the script fails loudly, and the server surfaces its text, rather
    /// than writing an empty file.
    /// </summary>
    [Fact]
    public async Task GeoPackageExportNamesTheMissingVectorLayers()
    {
        if (!QgisAvailable()) return;

        var ex = await Assert.ThrowsAsync<InvalidOperationException>(() => RunEntry("qgis_to_gpkg", SampleProject));

        Assert.Contains("no vector layers", ex.Message);
    }

    /// <summary>With the variable unset the launcher itself fails and names it.</summary>
    [Fact]
    public async Task UnsetVariableIsNamedByTheLauncher()
    {
        if (!OperatingSystem.IsWindows()) return; // a .cmd launcher only runs here

        var ex = await Assert.ThrowsAsync<InvalidOperationException>(
            () => RunEntry("qgis_to_pdf", SampleProject, withQgis: false));

        Assert.Contains("QGIS_PYTHON_CMD", ex.Message);
    }

    private static bool QgisAvailable() =>
        OperatingSystem.IsWindows() && QgisPython is not null && File.Exists(QgisPython);

    /// <summary>Mirror of the server's ScriptTranslator.ConfigureProcess for one entry.</summary>
    private static async Task<byte[]> RunEntry(string key, string input, bool withQgis = true)
    {
        var manifest = TranslatorManifest.Load(Path.Combine(PluginDir, TranslatorManifest.FileName));
        var entry = manifest.Translators.Single(t => t.Key == key);
        var output = Path.Combine(Path.GetTempPath(), $"nexus-qgis-{Guid.NewGuid():N}{entry.OutputFileExtension}");
        try
        {
            var psi = ExternalProcessRunner.CreateStartInfo(
                ManifestPlaceholders.Expand(entry.Command, string.Empty, string.Empty, PluginDir));
            foreach (var arg in entry.Args)
                psi.ArgumentList.Add(ManifestPlaceholders.Expand(arg, input, output, PluginDir));
            foreach (var (name, value) in entry.Env)
                psi.Environment[name] = ManifestPlaceholders.Expand(value, input, output, PluginDir);
            if (!withQgis) psi.Environment.Remove("QGIS_PYTHON_CMD");

            return await ExternalProcessRunner.RunAsync(
                psi, output, TimeSpan.FromSeconds(entry.TimeoutSeconds ?? 300), entry.Label, CancellationToken.None);
        }
        finally
        {
            if (File.Exists(output)) File.Delete(output);
        }
    }
}
