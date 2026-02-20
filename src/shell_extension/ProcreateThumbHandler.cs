/*
 * ProcreateThumbHandler.cs
 * ========================
 * Windows Shell Thumbnail Provider for .procreate files.
 * 
 * .procreate files are ZIP archives containing QuickLook/Thumbnail.png.
 * This COM DLL extracts that PNG and provides it to Windows Explorer
 * so that thumbnails appear in folder views (icons, tiles, etc.).
 *
 * Compile with:
 *   C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe
 *     /target:library /out:ProcreateThumbHandler.dll
 *     /reference:System.Drawing.dll
 *     ProcreateThumbHandler.cs
 *
 * Register with (Admin):
 *   C:\Windows\Microsoft.NET\Framework64\v4.0.30319\RegAsm.exe
 *     /codebase ProcreateThumbHandler.dll
 *
 * License: MIT
 */

using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Runtime.InteropServices.ComTypes;
using Microsoft.Win32;

namespace ProcreateThumbHandler
{
    // ── COM Interface: IThumbnailProvider ──────────────────────────────
    [ComImport]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    [Guid("e357fccd-a995-4576-b01f-234630154e96")]
    public interface IThumbnailProvider
    {
        void GetThumbnail(uint cx, out IntPtr phbmp, out uint pdwAlpha);
    }

    // ── COM Interface: IInitializeWithStream ──────────────────────────
    [ComImport]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    [Guid("b824b49d-22ac-4161-ac8a-9916e8fa3f7f")]
    public interface IInitializeWithStream
    {
        void Initialize(IStream pstream, uint grfMode);
    }

    // ── COM Interface: IInitializeWithFile (fallback) ─────────────────
    [ComImport]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    [Guid("b7d14566-0509-4cce-a71f-0a554233bd9b")]
    public interface IInitializeWithFile
    {
        void Initialize([MarshalAs(UnmanagedType.LPWStr)] string pszFilePath, uint grfMode);
    }

    // ── Thumbnail Provider Implementation ─────────────────────────────
    [ComVisible(true)]
    [Guid("C3A1B2D4-E5F6-4890-ABCD-123456789ABC")]
    [ClassInterface(ClassInterfaceType.None)]
    public class ProcreateThumbProvider : IThumbnailProvider, IInitializeWithStream, IInitializeWithFile
    {
        private IStream _stream;
        private string _filePath;

        // IInitializeWithStream
        public void Initialize(IStream pstream, uint grfMode)
        {
            _stream = pstream;
        }

        // IInitializeWithFile
        public void Initialize(string pszFilePath, uint grfMode)
        {
            _filePath = pszFilePath;
        }

        public void GetThumbnail(uint cx, out IntPtr phbmp, out uint pdwAlpha)
        {
            phbmp = IntPtr.Zero;
            pdwAlpha = 0;

            try
            {
                byte[] pngData = null;

                // Try file path first (most reliable)
                if (!string.IsNullOrEmpty(_filePath) && File.Exists(_filePath))
                {
                    pngData = ExtractThumbnailFromFile(_filePath);
                }

                // Fall back to stream
                if (pngData == null && _stream != null)
                {
                    byte[] zipData = ReadAllFromStream(_stream);
                    if (zipData != null && zipData.Length > 0)
                    {
                        pngData = ExtractThumbnailFromZipBytes(zipData);
                    }
                }

                if (pngData == null || pngData.Length == 0)
                    return;

                using (MemoryStream ms = new MemoryStream(pngData))
                using (Bitmap original = new Bitmap(ms))
                {
                    int targetSize = (int)cx;
                    if (targetSize < 1) targetSize = 256;

                    float scale = Math.Min(
                        (float)targetSize / original.Width,
                        (float)targetSize / original.Height
                    );

                    int newW = Math.Max(1, (int)(original.Width * scale));
                    int newH = Math.Max(1, (int)(original.Height * scale));

                    Bitmap thumb = new Bitmap(newW, newH, PixelFormat.Format32bppArgb);
                    using (Graphics g = Graphics.FromImage(thumb))
                    {
                        g.InterpolationMode = InterpolationMode.HighQualityBicubic;
                        g.SmoothingMode = SmoothingMode.HighQuality;
                        g.PixelOffsetMode = PixelOffsetMode.HighQuality;
                        g.CompositingQuality = CompositingQuality.HighQuality;
                        g.DrawImage(original, 0, 0, newW, newH);
                    }

                    phbmp = thumb.GetHbitmap(Color.Transparent);
                    pdwAlpha = 2; // WTSAT_ARGB
                }
            }
            catch
            {
                // Silently fail - Explorer shows default icon
            }
        }

        // ── Extract thumbnail by reading file as bytes ────────────────
        private static byte[] ExtractThumbnailFromFile(string filePath)
        {
            try
            {
                byte[] allBytes = File.ReadAllBytes(filePath);
                return ExtractThumbnailFromZipBytes(allBytes);
            }
            catch
            {
                return null;
            }
        }

        // ── Manual ZIP parser (no System.IO.Compression dependency) ───
        private static byte[] ExtractThumbnailFromZipBytes(byte[] zipData)
        {
            try
            {
                string[] targets = {
                    "QuickLook/Thumbnail.png",
                    "QuickLook/thumbnail.png",
                    "Thumbnail.png"
                };

                int eocdPos = FindEOCD(zipData);
                if (eocdPos < 0) return null;

                int totalEntries = ReadUInt16(zipData, eocdPos + 10);
                int cdOffset = (int)ReadUInt32(zipData, eocdPos + 16);

                int pos = cdOffset;
                for (int i = 0; i < totalEntries && pos + 46 < zipData.Length; i++)
                {
                    if (zipData[pos] != 0x50 || zipData[pos + 1] != 0x4B ||
                        zipData[pos + 2] != 0x01 || zipData[pos + 3] != 0x02)
                        break;

                    int compMethod = ReadUInt16(zipData, pos + 10);
                    int compSize = (int)ReadUInt32(zipData, pos + 20);
                    int uncompSize = (int)ReadUInt32(zipData, pos + 24);
                    int nameLen = ReadUInt16(zipData, pos + 28);
                    int extraLen = ReadUInt16(zipData, pos + 30);
                    int commentLen = ReadUInt16(zipData, pos + 32);
                    int localHeaderOffset = (int)ReadUInt32(zipData, pos + 42);

                    string name = System.Text.Encoding.UTF8.GetString(
                        zipData, pos + 46, nameLen);

                    bool isTarget = false;
                    foreach (string t in targets)
                    {
                        if (name.Equals(t, StringComparison.OrdinalIgnoreCase))
                        {
                            isTarget = true;
                            break;
                        }
                    }

                    if (!isTarget &&
                        name.StartsWith("QuickLook/", StringComparison.OrdinalIgnoreCase) &&
                        name.EndsWith(".png", StringComparison.OrdinalIgnoreCase))
                    {
                        isTarget = true;
                    }

                    if (isTarget)
                    {
                        byte[] data = ReadLocalEntry(
                            zipData, localHeaderOffset, compMethod, compSize, uncompSize);
                        if (data != null && data.Length > 0)
                            return data;
                    }

                    pos += 46 + nameLen + extraLen + commentLen;
                }

                return null;
            }
            catch
            {
                return null;
            }
        }

        private static byte[] ReadLocalEntry(
            byte[] zipData, int offset, int compMethod, int compSize, int uncompSize)
        {
            try
            {
                if (offset + 30 > zipData.Length) return null;
                if (zipData[offset] != 0x50 || zipData[offset + 1] != 0x4B ||
                    zipData[offset + 2] != 0x03 || zipData[offset + 3] != 0x04)
                    return null;

                int localNameLen = ReadUInt16(zipData, offset + 26);
                int localExtraLen = ReadUInt16(zipData, offset + 28);
                int dataStart = offset + 30 + localNameLen + localExtraLen;

                if (compMethod == 0) // Stored
                {
                    int size = uncompSize > 0 ? uncompSize : compSize;
                    if (dataStart + size > zipData.Length) return null;
                    byte[] data = new byte[size];
                    Array.Copy(zipData, dataStart, data, 0, size);
                    return data;
                }
                else if (compMethod == 8) // Deflate
                {
                    if (dataStart + compSize > zipData.Length) return null;
                    byte[] compressed = new byte[compSize];
                    Array.Copy(zipData, dataStart, compressed, 0, compSize);
                    return DeflateDecompress(compressed, uncompSize);
                }

                return null;
            }
            catch
            {
                return null;
            }
        }

        private static byte[] DeflateDecompress(byte[] data, int expectedSize)
        {
            try
            {
                using (MemoryStream input = new MemoryStream(data))
                using (System.IO.Compression.DeflateStream deflate =
                    new System.IO.Compression.DeflateStream(
                        input, System.IO.Compression.CompressionMode.Decompress))
                using (MemoryStream output = new MemoryStream())
                {
                    byte[] buffer = new byte[8192];
                    int read;
                    while ((read = deflate.Read(buffer, 0, buffer.Length)) > 0)
                    {
                        output.Write(buffer, 0, read);
                    }
                    return output.ToArray();
                }
            }
            catch
            {
                return null;
            }
        }

        // ── ZIP helpers ───────────────────────────────────────────────
        private static int FindEOCD(byte[] data)
        {
            for (int i = data.Length - 22;
                 i >= Math.Max(0, data.Length - 65557); i--)
            {
                if (data[i] == 0x50 && data[i + 1] == 0x4B &&
                    data[i + 2] == 0x05 && data[i + 3] == 0x06)
                    return i;
            }
            return -1;
        }

        private static int ReadUInt16(byte[] d, int o)
        {
            return d[o] | (d[o + 1] << 8);
        }

        private static uint ReadUInt32(byte[] d, int o)
        {
            return (uint)(d[o] | (d[o + 1] << 8) |
                          (d[o + 2] << 16) | (d[o + 3] << 24));
        }

        // ── Read COM IStream ─────────────────────────────────────────
        private static byte[] ReadAllFromStream(IStream stream)
        {
            try
            {
                System.Runtime.InteropServices.ComTypes.STATSTG stat;
                stream.Stat(out stat, 1);
                long size = stat.cbSize;
                if (size <= 0 || size > 500L * 1024 * 1024) return null;

                byte[] buffer = new byte[size];
                IntPtr newPosPtr = Marshal.AllocCoTaskMem(8);
                try { stream.Seek(0, 0, newPosPtr); }
                finally { Marshal.FreeCoTaskMem(newPosPtr); }

                IntPtr bytesReadPtr = Marshal.AllocCoTaskMem(sizeof(int));
                try
                {
                    stream.Read(buffer, (int)size, bytesReadPtr);
                }
                finally
                {
                    Marshal.FreeCoTaskMem(bytesReadPtr);
                }
                return buffer;
            }
            catch
            {
                return null;
            }
        }
    }

    // ── COM Self-Registration ─────────────────────────────────────────
    [ComVisible(false)]
    public static class ShellRegistration
    {
        private const string CLSID = "{C3A1B2D4-E5F6-4890-ABCD-123456789ABC}";
        private const string Extension = ".procreate";
        private const string HandlerName = "Procreate Thumbnail Handler";
        private const string ThumbGuid = "{e357fccd-a995-4576-b01f-234630154e96}";

        [ComRegisterFunction]
        public static void Register(Type type)
        {
            try
            {
                // Register thumbnail handler for .procreate
                using (RegistryKey key = Registry.ClassesRoot.CreateSubKey(
                    Extension + @"\ShellEx\" + ThumbGuid))
                {
                    if (key != null) key.SetValue(null, CLSID);
                }

                using (RegistryKey key = Registry.LocalMachine.CreateSubKey(
                    @"Software\Classes\" + Extension + @"\ShellEx\" + ThumbGuid))
                {
                    if (key != null) key.SetValue(null, CLSID);
                }

                // Approved extensions
                using (RegistryKey key = Registry.LocalMachine.OpenSubKey(
                    @"Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Approved",
                    true))
                {
                    if (key != null) key.SetValue(CLSID, HandlerName);
                }

                // Extension metadata
                using (RegistryKey key = Registry.ClassesRoot.CreateSubKey(Extension))
                {
                    if (key != null)
                    {
                        key.SetValue("Content Type", "application/x-procreate");
                        key.SetValue("PerceivedType", "image");
                    }
                }

                // Disable process isolation for in-process loading
                using (RegistryKey key = Registry.ClassesRoot.CreateSubKey(
                    @"CLSID\" + CLSID))
                {
                    if (key != null)
                        key.SetValue("DisableProcessIsolation", 1,
                                     RegistryValueKind.DWord);
                }

                SHChangeNotify(0x08000000, 0, IntPtr.Zero, IntPtr.Zero);

                Console.WriteLine("SUCCESS: Procreate thumbnail handler registered!");
                Console.WriteLine("Restart Explorer or log out/in to see thumbnails.");
            }
            catch (Exception ex)
            {
                Console.Error.WriteLine("Registration error: " + ex.Message);
            }
        }

        [ComUnregisterFunction]
        public static void Unregister(Type type)
        {
            try
            {
                string sk = Extension + @"\ShellEx\" + ThumbGuid;
                try { Registry.ClassesRoot.DeleteSubKeyTree(sk, false); } catch { }
                try { Registry.LocalMachine.DeleteSubKeyTree(
                    @"Software\Classes\" + sk, false); } catch { }
                using (RegistryKey key = Registry.LocalMachine.OpenSubKey(
                    @"Software\Microsoft\Windows\CurrentVersion\Shell Extensions\Approved",
                    true))
                {
                    try { if (key != null) key.DeleteValue(CLSID, false); } catch { }
                }
                SHChangeNotify(0x08000000, 0, IntPtr.Zero, IntPtr.Zero);
                Console.WriteLine("Procreate thumbnail handler unregistered.");
            }
            catch { }
        }

        [DllImport("shell32.dll")]
        private static extern void SHChangeNotify(
            uint wEventId, uint uFlags, IntPtr dwItem1, IntPtr dwItem2);
    }
}
