using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Text;

namespace CarolineConsole
{
    /// <summary>
    /// Minimal JSON serializer/deserializer - no external dependencies.
    /// </summary>
    public static class SimpleJson
    {
        #region Serialization

        public static string Serialize(object obj)
        {
            var sb = new StringBuilder();
            SerializeValue(sb, obj);
            return sb.ToString();
        }

        private static void SerializeValue(StringBuilder sb, object val)
        {
            if (val == null)
            {
                sb.Append("null");
            }
            else if (val is bool)
            {
                sb.Append((bool)val ? "true" : "false");
            }
            else if (val is string)
            {
                SerializeString(sb, (string)val);
            }
            else if (val is int || val is long || val is short || val is byte)
            {
                sb.Append(val.ToString());
            }
            else if (val is float)
            {
                sb.Append(((float)val).ToString("G", CultureInfo.InvariantCulture));
            }
            else if (val is double)
            {
                sb.Append(((double)val).ToString("G", CultureInfo.InvariantCulture));
            }
            else if (val is Dictionary<string, object>)
            {
                SerializeDict(sb, (Dictionary<string, object>)val);
            }
            else if (val is IList)
            {
                SerializeList(sb, (IList)val);
            }
            else
            {
                // Fallback: treat as string
                SerializeString(sb, val.ToString());
            }
        }

        private static void SerializeString(StringBuilder sb, string s)
        {
            sb.Append('"');
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < ' ')
                            sb.AppendFormat("\\u{0:X4}", (int)c);
                        else
                            sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
        }

        private static void SerializeDict(StringBuilder sb, Dictionary<string, object> dict)
        {
            sb.Append('{');
            bool first = true;
            foreach (var kv in dict)
            {
                if (!first) sb.Append(',');
                first = false;
                SerializeString(sb, kv.Key);
                sb.Append(':');
                SerializeValue(sb, kv.Value);
            }
            sb.Append('}');
        }

        private static void SerializeList(StringBuilder sb, IList list)
        {
            sb.Append('[');
            for (int i = 0; i < list.Count; i++)
            {
                if (i > 0) sb.Append(',');
                SerializeValue(sb, list[i]);
            }
            sb.Append(']');
        }

        #endregion

        #region Deserialization

        public static Dictionary<string, object> Deserialize(string json)
        {
            if (string.IsNullOrEmpty(json)) return null;
            int index = 0;
            SkipWhitespace(json, ref index);
            if (index < json.Length && json[index] == '{')
            {
                return ParseObject(json, ref index);
            }
            return null;
        }

        private static void SkipWhitespace(string json, ref int index)
        {
            while (index < json.Length && char.IsWhiteSpace(json[index]))
                index++;
        }

        private static Dictionary<string, object> ParseObject(string json, ref int index)
        {
            var dict = new Dictionary<string, object>();
            index++; // skip {
            SkipWhitespace(json, ref index);

            if (index < json.Length && json[index] == '}')
            {
                index++;
                return dict;
            }

            while (index < json.Length)
            {
                SkipWhitespace(json, ref index);
                string key = ParseString(json, ref index);
                SkipWhitespace(json, ref index);
                if (index < json.Length && json[index] == ':') index++;
                SkipWhitespace(json, ref index);
                object value = ParseValue(json, ref index);
                dict[key] = value;
                SkipWhitespace(json, ref index);
                if (index < json.Length && json[index] == ',')
                {
                    index++;
                    continue;
                }
                if (index < json.Length && json[index] == '}')
                {
                    index++;
                    break;
                }
                break;
            }
            return dict;
        }

        private static object ParseValue(string json, ref int index)
        {
            SkipWhitespace(json, ref index);
            if (index >= json.Length) return null;

            char c = json[index];
            if (c == '"') return ParseString(json, ref index);
            if (c == '{') return ParseObject(json, ref index);
            if (c == '[') return ParseArray(json, ref index);
            if (c == 't' || c == 'f') return ParseBool(json, ref index);
            if (c == 'n') { index += 4; return null; }
            return ParseNumber(json, ref index);
        }

        private static string ParseString(string json, ref int index)
        {
            index++; // skip opening "
            var sb = new StringBuilder();
            while (index < json.Length)
            {
                char c = json[index++];
                if (c == '"') break;
                if (c == '\\' && index < json.Length)
                {
                    char next = json[index++];
                    switch (next)
                    {
                        case '"': sb.Append('"'); break;
                        case '\\': sb.Append('\\'); break;
                        case 'n': sb.Append('\n'); break;
                        case 'r': sb.Append('\r'); break;
                        case 't': sb.Append('\t'); break;
                        case 'u':
                            if (index + 4 <= json.Length)
                            {
                                string hex = json.Substring(index, 4);
                                sb.Append((char)int.Parse(hex, NumberStyles.HexNumber));
                                index += 4;
                            }
                            break;
                        default: sb.Append(next); break;
                    }
                }
                else
                {
                    sb.Append(c);
                }
            }
            return sb.ToString();
        }

        private static List<object> ParseArray(string json, ref int index)
        {
            var list = new List<object>();
            index++; // skip [
            SkipWhitespace(json, ref index);
            if (index < json.Length && json[index] == ']') { index++; return list; }

            while (index < json.Length)
            {
                list.Add(ParseValue(json, ref index));
                SkipWhitespace(json, ref index);
                if (index < json.Length && json[index] == ',') { index++; continue; }
                if (index < json.Length && json[index] == ']') { index++; break; }
                break;
            }
            return list;
        }

        private static bool ParseBool(string json, ref int index)
        {
            if (json[index] == 't') { index += 4; return true; }
            index += 5; return false;
        }

        private static object ParseNumber(string json, ref int index)
        {
            int start = index;
            while (index < json.Length && (char.IsDigit(json[index]) || json[index] == '.' || json[index] == '-' || json[index] == '+' || json[index] == 'e' || json[index] == 'E'))
                index++;
            string num = json.Substring(start, index - start);
            if (num.Contains(".") || num.Contains("e") || num.Contains("E"))
            {
                double d;
                double.TryParse(num, NumberStyles.Float, CultureInfo.InvariantCulture, out d);
                return d;
            }
            int i;
            if (int.TryParse(num, out i)) return i;
            long l;
            if (long.TryParse(num, out l)) return l;
            return 0;
        }

        #endregion

        #region Helper: Build response dictionaries easily

        public static Dictionary<string, object> Obj()
        {
            return new Dictionary<string, object>();
        }

        public static Dictionary<string, object> OkResponse(object data)
        {
            var d = new Dictionary<string, object>();
            d["ok"] = true;
            d["data"] = data;
            return d;
        }

        public static Dictionary<string, object> ErrorResponse(string error)
        {
            var d = new Dictionary<string, object>();
            d["ok"] = false;
            d["error"] = error;
            return d;
        }

        #endregion
    }
}
