const togpx = require('togpx')
const reproject = require('reproject')
const epsg = require('epsg')
const fs = require('fs')

let inputfiles = fs.globSync('*/*.geojson')

for (let inputfile of inputfiles) {
	console.log(inputfile)
	let geojson = JSON.parse(fs.readFileSync(inputfile, 'utf8'))
	geojson = reproject.toWgs84(geojson, undefined, epsg)
	let gpx = togpx(geojson)
	outputfile = inputfile.replace('.geojson', '.gpx')
	fs.writeFileSync(outputfile, gpx)
}
