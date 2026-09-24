using System.Globalization;
using System.Windows.Media;
using System.Windows.Media.Media3D;

namespace ReXtremeSDK.Preview;

public static class ObjPreviewLoader
{
    public static GeometryModel3D Load(string file)
    {
        var vertices = new List<Point3D>();
        var positions = new Point3DCollection();
        var triangles = new Int32Collection();

        foreach (var raw in File.ReadLines(file))
        {
            var line = raw.Trim();
            if (line.StartsWith("v ", StringComparison.Ordinal))
            {
                var p = line.Split(' ', StringSplitOptions.RemoveEmptyEntries);
                if (p.Length >= 4)
                    vertices.Add(new Point3D(Parse(p[1]), Parse(p[2]), Parse(p[3])));
            }
            else if (line.StartsWith("f ", StringComparison.Ordinal))
            {
                var face = line.Split(' ', StringSplitOptions.RemoveEmptyEntries)
                    .Skip(1)
                    .Select(token => token.Split('/')[0])
                    .Select(v => int.Parse(v, CultureInfo.InvariantCulture))
                    .Select(v => v > 0 ? v - 1 : vertices.Count + v)
                    .ToArray();

                if (face.Length < 3) continue;
                for (var i = 1; i < face.Length - 1; i++)
                {
                    AddVertex(face[0]);
                    AddVertex(face[i]);
                    AddVertex(face[i + 1]);
                }
            }
        }

        if (positions.Count == 0)
            throw new InvalidDataException("OBJ não contém faces suportadas pelo preview inicial.");

        Normalize(positions);

        var mesh = new MeshGeometry3D
        {
            Positions = positions,
            TriangleIndices = triangles
        };
        var material = new DiffuseMaterial(new SolidColorBrush(Color.FromRgb(145, 150, 158)));
        return new GeometryModel3D(mesh, material) { BackMaterial = material };

        void AddVertex(int index)
        {
            if (index < 0 || index >= vertices.Count)
                throw new InvalidDataException("Índice OBJ fora da faixa.");
            triangles.Add(positions.Count);
            positions.Add(vertices[index]);
        }
    }

    private static double Parse(string value) =>
        double.Parse(value, NumberStyles.Float, CultureInfo.InvariantCulture);

    private static void Normalize(Point3DCollection points)
    {
        var minX = points.Min(p => p.X); var maxX = points.Max(p => p.X);
        var minY = points.Min(p => p.Y); var maxY = points.Max(p => p.Y);
        var minZ = points.Min(p => p.Z); var maxZ = points.Max(p => p.Z);
        var center = new Point3D((minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2);
        var size = Math.Max(maxX - minX, Math.Max(maxY - minY, maxZ - minZ));
        if (size <= 0) size = 1;
        var scale = 3.5 / size;

        for (var i = 0; i < points.Count; i++)
        {
            var p = points[i];
            points[i] = new Point3D(
                (p.X - center.X) * scale,
                (p.Y - center.Y) * scale,
                (p.Z - center.Z) * scale);
        }
    }
}
