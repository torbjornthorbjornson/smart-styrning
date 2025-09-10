# Logga in
$LoginUrl   = 'https://arrigo.svenskastenhus.se/arrigo/api/login'
$GraphqlUrl = 'https://arrigo.svenskastenhus.se/arrigo/api/graphql'
$User       = 'APIUser'
$Pass       = 'API_S#are'

$tok = (Invoke-RestMethod -Uri $LoginUrl -Method POST -ContentType 'application/json' `
        -Body (@{username=$User;password=$Pass} | ConvertTo-Json)).authToken
$hdr = @{ Authorization = "Bearer $tok"; 'Content-Type'='application/json' }

# Läs variabler under din PVL
$PVL_CLEAR = 'APIdemo.AreaFolderView.File.APIVaribleList.File'
$PVL_B64   = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($PVL_CLEAR))

$qRead = @'
query($path:String!){
  data(path:$path){
    variables { technicalAddress value }
  }
}
'@

$vars = (Invoke-RestMethod -Uri $GraphqlUrl -Method POST -Headers $hdr `
          -Body (@{ query=$qRead; variables=@{ path=$PVL_B64 } } | ConvertTo-Json -Depth 5 -Compress)).data.data.variables

$vars | Select-Object -First 10 technicalAddress,value
