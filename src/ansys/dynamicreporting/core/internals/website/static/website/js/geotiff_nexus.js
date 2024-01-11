function nexus_image_general_error(error) {
    console.log(error);
}

function nexus_image_load_pick_buffer(name, pick_buffer_image) {
    let array_promise = pick_buffer_image.readRasters({interleave: true});
    array_promise.then(nexus_image_load_pick_buffer_array.bind(null, name), nexus_image_general_error);
}

function nexus_image_load_pick_buffer_array(name, pick_buffer_array) {
    let image_elem = document.getElementById(name);
    image_elem.nexus_pick_buffer = pick_buffer_array;
}

function nexus_image_load_var_buffer(name, var_buffer_image) {
    let array_promise = var_buffer_image.readRasters({interleave: true});
    array_promise.then(nexus_image_load_var_buffer_array.bind(null, name), nexus_image_general_error);
}

function nexus_image_load_var_buffer_array(name, var_buffer_array) {
    let image_elem = document.getElementById(name);
    image_elem.nexus_var_buffer = var_buffer_array;
}

async function nexus_image_load_tiff_image(name, tiff) {
    const image = await tiff.getImage(0);
    const width = image.getWidth();
    const height = image.getHeight();
    const directory = await image.getFileDirectory();
    const rawbuffer = await image.readRasters({interleave: true});

    const utf8_metadata = directory.ImageDescription.slice(0, -1);
    const metadata = JSON.parse(utf8_metadata);

    let buffer = new Uint8ClampedArray(width * height * 4);
    for (let y = 0; y < height; y++) {
        let pos_out = (y * width) * 4;
        let pos_in = (y * width) * 3;
        for (let x = 0; x < width; x++) {
            buffer[pos_out++] = rawbuffer[pos_in++];
            buffer[pos_out++] = rawbuffer[pos_in++];
            buffer[pos_out++] = rawbuffer[pos_in++];
            buffer[pos_out++] = 255;
        }
    }

    let canvas = document.createElement('canvas');
    let ctx = canvas.getContext('2d');
    canvas.width = width;
    canvas.height = height;
    let image_data = ctx.createImageData(width, height);
    image_data.data.set(buffer);
    ctx.putImageData(image_data, 0, 0);

    let image_elem = document.getElementById(name);
    image_elem.src = canvas.toDataURL();
    image_elem.canvas = canvas;
    image_elem.nexus_width = width;
    image_elem.nexus_height = height;

    let coordLookup = {
        1: 'X',
        2: 'Y',
        3: 'Z'
    };
    let varMap = {};
    for (const varDef of metadata.variables) {
        // split vector quantities into scalars
        // a variable with a subpal_minmax of keys [0,1,2,3]
        // is considered a vector. We split that into their
        // own scalar values. Eg: 'Velocity' with id of '9'
        // will be split into 'Velocity','Velocity[X]','Velocity[Y]',
        // 'Velocity[Z]' with ids '9','9-X','9-Y','9-Z'.
        if ('subpal_minmax' in varDef) {
            const subpalMinmax = varDef['subpal_minmax'];
            if (Object.keys(subpalMinmax).length > 0) {
                // magnitude's minmax
                varDef['subpal_minmax'] = subpalMinmax[0];
                // check for vectors
                if (Object.keys(subpalMinmax).length === 4) {
                    const name = varDef['name'];
                    for (let i = 1; i <= Object.keys(coordLookup).length; i++) {
                        let varDefCoord = {...varDef};
                        let coord = coordLookup[i];
                        varDefCoord['subpal_minmax'] = subpalMinmax[i];
                        varDefCoord['name'] = `${name}[${coord}]`;
                        varMap[`${varDef.pal_id}-${coord}`] = varDefCoord;
                    }
                }
            }
        }
        varMap[varDef.pal_id] = varDef;
    }

    let partMap = {};
    let varInfo = {};
    for (const partDef of metadata.parts) {
        const partIdx = parseInt(partDef.id);
        partMap[partIdx] = partDef;
        // find the variable in the part,
        // convert to vectors if needed
        // eg: colorby_var of '9.2' will be made into '9-Y'
        // and later used to lookup in the varMap to get
        // 'Velocity[Y]' and the associated varInfo.
        let [varIdx, minmaxId] = partDef.colorby_var.split('.');
        if (minmaxId in coordLookup) {
            varIdx = `${varIdx}-${coordLookup[parseInt(minmaxId)]}`;
        }
        if (varIdx in varMap) {
            varInfo[varIdx] = varMap[varIdx];
            partMap[partIdx].variable = varIdx;
        }
    }
    image_elem.nexus_metadata = partMap;
    image_elem.nexus_varinfo = varInfo;

    let pick_image_promise = tiff.getImage(1);
    pick_image_promise.then(nexus_image_load_pick_buffer.bind(null, name), nexus_image_general_error);
    let var_image_promise = tiff.getImage(2);
    var_image_promise.then(nexus_image_load_var_buffer.bind(null, name), nexus_image_general_error);
}
