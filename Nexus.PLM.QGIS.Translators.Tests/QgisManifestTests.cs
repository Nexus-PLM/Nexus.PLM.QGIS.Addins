using Nexus.PLM.Addin.Sdk.Translators;
using Nexus.PLM.Addin.Sdk.Translators.Testing;
using Xunit;

namespace Nexus.PLM.QGIS.Translators.Tests;

/// <summary>
/// Contract tests for this repo's <c>translators/translators.json</c>: three project exports
/// over one PyQGIS script, export picked by the output extension.
/// </summary>
public class QgisManifestTests : ManifestContractTests
{
    /// <inheritdoc/>
    protected override string ManifestPath =>
        Path.Combine(AppContext.BaseDirectory, "translators", TranslatorManifest.FileName);

    /// <summary>The three keys reserved in the Services ownership table.</summary>
    [Fact]
    public void CarriesTheThreeReservedKeys() =>
        Assert.Equal(
            ["qgis_to_gpkg", "qgis_to_pdf", "qgis_to_png"],
            Load().Translators.Select(t => t.Key).OrderBy(k => k).ToArray());

    /// <summary>
    /// Every entry runs the launcher beside the manifest, never the interpreter directly: the
    /// interpreter's default path has spaces and cmd's /C quote rule breaks on it. Paths and
    /// the offscreen platform travel through env vars. Hold the exact shape.
    /// </summary>
    [Fact]
    public void EveryEntryRunsTheLauncherWithPathsInEnv()
    {
        foreach (var t in Load().Translators)
        {
            Assert.Equal("${dir}/qgis_export.cmd", t.Command);
            Assert.Empty(t.Args);
            Assert.Equal("${input}", t.Env["QGIS_INPUT"]);
            Assert.Equal("${output}", t.Env["QGIS_OUTPUT"]);
            Assert.Equal("offscreen", t.Env["QT_QPA_PLATFORM"]);
            Assert.Equal("application/x-qgis-project", t.InputMimeType);
            Assert.Equal(".qgz", t.InputFileExtension);
            Assert.True(t.TimeoutSeconds >= 300, "a cold OSGeo4W start takes a while");
        }
    }

    /// <summary>The launcher and the export script sit beside the manifest, where
    /// <c>${dir}</c> resolves, and stay ASCII (console output goes through the system code page).</summary>
    [Fact]
    public void TheLauncherAndScriptSitBesideTheManifest_AndAreAscii()
    {
        var dir = Path.GetDirectoryName(ManifestPath)!;
        var launcher = Path.Combine(dir, "qgis_export.cmd");
        var script = Path.Combine(dir, "qgis_export.py");

        Assert.True(File.Exists(launcher));
        Assert.True(File.Exists(script));
        foreach (var file in new[] { launcher, script })
            Assert.False(File.ReadAllText(file).Any(c => c > 127), "non-ASCII in " + Path.GetFileName(file));

        var cmd = File.ReadAllText(launcher);
        Assert.Contains("call \"%QGIS_PYTHON_CMD%\"", cmd);
        var py = File.ReadAllText(script);
        Assert.Contains("QGIS_INPUT", py);
        Assert.Contains("QGIS_OUTPUT", py);
        foreach (var ext in new[] { ".pdf", ".png", ".gpkg" })
            Assert.Contains("\"" + ext + "\"", py);
    }

    /// <summary>The launcher fails loudly, naming the variable, when QGIS is not configured:
    /// the Translation server reports that text instead of "produced no output".</summary>
    [Fact]
    public void TheLauncherNamesTheVariableWhenUnset()
    {
        var cmd = File.ReadAllText(Path.Combine(Path.GetDirectoryName(ManifestPath)!, "qgis_export.cmd"));
        Assert.Contains("if not defined QGIS_PYTHON_CMD", cmd);
        Assert.Contains("exit /b 2", cmd);
    }
}
