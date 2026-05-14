Shader "Placeholder/VertexColor"
{
    Properties
    {
        _Glossiness ("Smoothness", Range(0,1)) = 0.1
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 100

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            half _Glossiness;

            struct appdata
            {
                float4 vertex : POSITION;
                float4 color : COLOR;
                float3 normal : NORMAL;
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float4 color : COLOR;
                float3 worldNormal : TEXCOORD0;
            };

            v2f vert(appdata v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.color = v.color;
                o.worldNormal = UnityObjectToWorldNormal(v.normal);
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float3 lightDir = normalize(_WorldSpaceLightPos0.xyz);
                float ndl = max(0.2, dot(i.worldNormal, lightDir));
                return fixed4(i.color.rgb * ndl, 1.0);
            }
            ENDCG
        }
    }
    FallBack "Diffuse"
}
