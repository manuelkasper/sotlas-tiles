<?php

$fd = fopen("summitslist.csv", "r");

$version = fgets($fd);
$header = array_flip(fgetcsv($fd));
$now = date("Y-m-d");

$regions = [];
$padding = 1;	// km

$summitsfd = fopen("summits.geojson", "w");
$inactivesummitsfd = fopen("summits_inactive.geojson", "w");
$numsummits = 0;
while ($flds = fgetcsv($fd)) {
	$inactive = false;
	if ($now < convertDate($flds[$header['ValidFrom']]) || $now > convertDate($flds[$header['ValidTo']])) {
		//echo "summit " . $flds[$header['SummitCode']] . " currently invalid (" . $flds[$header['ValidFrom']] . " - " . $flds[$header['ValidTo']] . ")\n";
		$inactive = true;
	}

	if (!preg_match("/^(.+\/.+)-(.+)$/", $flds[$header['SummitCode']], $matches)) {
		//echo "NO MATCH\n";
		continue;
	}

	$region = $matches[1];

	if (!@$regions[$region]) {
		$regions[$region] = [(double)$flds[$header['Longitude']], (double)$flds[$header['Latitude']], (double)$flds[$header['Longitude']], (double)$flds[$header['Latitude']]];
	} else {
		$regions[$region][0] = min($regions[$region][0], (double)$flds[$header['Longitude']]);
		$regions[$region][1] = min($regions[$region][1], (double)$flds[$header['Latitude']]);
		$regions[$region][2] = max($regions[$region][2], (double)$flds[$header['Longitude']]);
		$regions[$region][3] = max($regions[$region][3], (double)$flds[$header['Latitude']]);
	}

	$feature = [
		"type" => "Feature",
		"properties" => ["code" => $flds[$header['SummitCode']], "name" => $flds[$header['SummitName']], "alt" => (int)$flds[$header['AltM']], "points" => (int)$flds[$header['Points']], "act" => (int)$flds[$header['ActivationCount']]],
		"geometry" => [
			"type" => "Point",
			"coordinates" => [(double)$flds[$header['Longitude']], (double)$flds[$header['Latitude']]]
		]
	];

	if ($inactive) {
		fprintf($inactivesummitsfd, json_encode($feature) . "\n");
	} else {
		fprintf($summitsfd, json_encode($feature) . "\n");
	}
	$numsummits++;
}
fclose($summitsfd);
fclose($inactivesummitsfd);

if ($numsummits < 100000) {
	fwrite(STDERR, "Unexpected number of summits $numsummits\n");
	exit(1);
}

$out = fopen("regions_areas.geojson", "w");
foreach ($regions as $region => &$bbox) {
	// add padding
	$bbox[0] -= $padding / (cos(deg2rad($bbox[1])) * 111.32);
	$bbox[1] -= $padding / 111.32;
	$bbox[2] += $padding / (cos(deg2rad($bbox[1])) * 111.32);
	$bbox[3] += $padding / 111.32;

	$feature = [
		"type" => "Feature",
		"properties" => ["region" => $region],
		"geometry" => [
			"type" => "Polygon",
			"coordinates" => [[
				[$bbox[0], $bbox[1]],
				[$bbox[0], $bbox[3]],
				[$bbox[2], $bbox[3]],
				[$bbox[2], $bbox[1]]
			]]
		]
	];

	fprintf($out, json_encode($feature) . "\n");
}
fclose($out);

$out = fopen("regions_labels.geojson", "w");
foreach ($regions as $region => $bbox) {
	$feature = [
		"type" => "Feature",
		"properties" => ["region" => $region],
		"geometry" => [
			"type" => "Point",
			"coordinates" => [$bbox[0], $bbox[3]]
		]
	];

	fprintf($out, json_encode($feature) . "\n");
}
fclose($out);


function convertDate($date) {
	if ($date === null)
		return null;

	$da = array_reverse(explode("/", $date));
	return join("-", $da);
}
