# arrigo_sanity_write_96.ps1
# Sanity-check för Arrigo API: togglar PRICE_OK, skriver test-rank 0..95
# och sätter slumpvärden på Price_Val + EC/EX-masker (32-bitars)

# ==== KONFIG ====
$LoginUrl   = 'https://arrigo.svenskastenhus.se/arrigo/api/login'
$GraphqlUrl = 'https://arrigo.svenskastenhus.se/arrigo/api/graphql'
$User       = 'APIUser'
$Pass       = 'API_S#are'
$PVL_CLEAR  = 'APIdemo.AreaFolderView.File.APIVaribleList.File'
$PVL_B64    = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($PVL_CLEAR))

# ==== LOGIN ====
$tok = (Invoke-RestMethod -Uri $LoginUrl -Method POST -ContentType 'application/json' `
  -Body (@{username=$User;password=$Pass} | ConvertTo-Json)).authToken
$hdr = @{ Authorization = "Bearer $tok"; 'Content-Type'='application/json' }

# ==== HJÄLPARE ====
function Invoke-JsonPost([string]$Url,[hashtable]$Headers,[hashtable]$Body){
  $json = $Body | ConvertTo-Json -Depth 20 -Compress
  Invoke-RestMethod -Uri $Url -Method POST -ContentType 'application/json' -Headers $Headers -Body $json
}

$mutation = 'mutation ($variables:[VariableKeyValue!]!){ writeData(variables:$variables) }'
function Write-Items($kv){
  $items = @()
  foreach($k in $kv.Keys){ $items += @{ key=$k; value="$($kv[$k])" } }
  Invoke-JsonPost -Url $GraphqlUrl -Headers $hdr -Body @{ query=$mutation; variables=@{ variables=$items } }
}

# ==== LÄS VARIABLER ====
$qRead = @'
query($path:String!){
  data(path:$path){
    variables { technicalAddress value }
  }
}
'@
$vars = (Invoke-JsonPost -Url $GraphqlUrl -Headers $hdr -Body @{ query=$qRead; variables=@{ path=$PVL_B64 } }).data.data.variables

# Bygg index
$IndexOf = @{}
for ($i=0; $i -lt $vars.Count; $i++) { $IndexOf[$vars[$i].technicalAddress] = $i }

$PriceOkTA = ($vars | Where-Object { $_.technicalAddress -like '*.PRICE_OK' } | Select-Object -First 1 -Expand technicalAddress)

$RankTA = @{}
$ValTA  = @{}
foreach($v in $vars){
  if ($v.technicalAddress -match '\.PRICE_RANK\((\d+)\)$') {
    $h = [int]$Matches[1]; $RankTA[$h] = $v.technicalAddress
  }
  if ($v.technicalAddress -match '\.PRICE_VAL\((\d+)\)$') {
    $h = [int]$Matches[1]; $ValTA[$h]  = $v.technicalAddress
  }
}

$EC32TA = @{}
$EX32TA = @{}
foreach($v in $vars){
  if ($v.technicalAddress -match '\.EC_MASK32_(\d+)$') {
    $EC32TA[[int]$Matches[1]] = $v.technicalAddress
  }
  if ($v.technicalAddress -match '\.EX_MASK32_(\d+)$') {
    $EX32TA[[int]$Matches[1]] = $v.technicalAddress
  }
}

# ==== BYGG BATCH ====
$kv = @{}

if ($PriceOkTA) {
  $keyOK = ('{0}:{1}' -f $PVL_B64, $IndexOf[$PriceOkTA])
  $kv[$keyOK] = 0   # gate ner
}

# Test-rank 0..95
$rank = 0..95
foreach($h in 0..95){
  if ($RankTA.ContainsKey($h)) {
    $keyH = ('{0}:{1}' -f $PVL_B64, $IndexOf[$RankTA[$h]])
    $kv[$keyH] = $rank[$h]
  }
}

# Test Price_Val (sätt t.ex. 0.10, 0.11, 0.12 ...)
foreach($h in 0..95){
  if ($ValTA.ContainsKey($h)) {
    $keyV = ('{0}:{1}' -f $PVL_B64, $IndexOf[$ValTA[$h]])
    $kv[$keyV] = [Math]::Round(0.10 + $h*0.01, 2)
  }
}

# Testmasker (slumpmässiga exempel)
$ecVals = @(12345, 67890, 13579)
$exVals = @(24680, 11111, 22222)
foreach($i in $EC32TA.Keys){
  $key = ('{0}:{1}' -f $PVL_B64, $IndexOf[$EC32TA[$i]])
  $kv[$key] = $ecVals[$i-1]
}
foreach($i in $EX32TA.Keys){
  $key = ('{0}:{1}' -f $PVL_B64, $IndexOf[$EX32TA[$i]])
  $kv[$key] = $exVals[$i-1]
}

# ==== SKRIV ====
Write-Items $kv | Out-Null
if ($PriceOkTA) {
  $keyOK = ('{0}:{1}' -f $PVL_B64, $IndexOf[$PriceOkTA])
  Write-Items @{ $keyOK = 1 } | Out-Null
}

# ==== VERIFIERA ====
$verify = (Invoke-JsonPost -Url $GraphqlUrl -Headers $hdr -Body @{ query=$qRead; variables=@{ path=$PVL_B64 } }).data.data.variables

$verify |
  Where-Object {
    $_.technicalAddress -like '*.PRICE_OK' -or
    $_.technicalAddress -match '\.PRICE_RANK\((\d+)\)$' -or
    $_.technicalAddress -match '\.PRICE_VAL\((\d+)\)$' -or
    $_.technicalAddress -match '\.(EC|EX)_MASK32_\d+$'
  } |
  Sort-Object technicalAddress |
  Select-Object -First 150 technicalAddress,value |
  Format-Table -AutoSize

"✅ Sanity-write klar. Skrev rank 0..95, Price_Val och EC/EX-masker."
