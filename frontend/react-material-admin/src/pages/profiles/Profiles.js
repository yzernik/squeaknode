import React, {useState, useEffect} from 'react';
import {useHistory} from "react-router-dom";
import {Grid, Button} from "@material-ui/core";
import MUIDataTable from "mui-datatables";

// styles
import {makeStyles} from '@material-ui/core/styles';

// components
import PageTitle from "../../components/PageTitle";
import Widget from "../../components/Widget";
import Table from "../dashboard/components/Table/Table";

// data
import mock from "../dashboard/mock";

import {GetInfoRequest} from "../../proto/lnd_pb"
import {HelloRequest, GetFollowedSqueakDisplaysRequest, GetSigningProfilesRequest} from "../../proto/squeak_admin_pb"
import {SqueakAdminClient} from "../../proto/squeak_admin_grpc_web_pb"

var client = new SqueakAdminClient('http://' + window.location.hostname + ':8080')

const datatableData = [
  [
    "Joe James", "Example Inc.", "Yonkers", "NY"
  ],
  [
    "John Walsh", "Example Inc.", "Hartford", "CT"
  ],
  [
    "Bob Herm", "Example Inc.", "Tampa", "FL"
  ],
  [
    "James Houston", "Example Inc.", "Dallas", "TX"
  ],
  [
    "Prabhakar Linwood", "Example Inc.", "Hartford", "CT"
  ],
  [
    "Kaui Ignace", "Example Inc.", "Yonkers", "NY"
  ],
  [
    "Esperanza Susanne", "Example Inc.", "Hartford", "CT"
  ],
  [
    "Christian Birgitte", "Example Inc.", "Tampa", "FL"
  ],
  [
    "Meral Elias", "Example Inc.", "Hartford", "CT"
  ],
  [
    "Deep Pau", "Example Inc.", "Yonkers", "NY"
  ],
  [
    "Sebastiana Hani", "Example Inc.", "Dallas", "TX"
  ],
  [
    "Marciano Oihana", "Example Inc.", "Yonkers", "NY"
  ],
  [
    "Brigid Ankur", "Example Inc.", "Dallas", "TX"
  ],
  [
    "Anna Siranush", "Example Inc.", "Yonkers", "NY"
  ],
  [
    "Avram Sylva", "Example Inc.", "Hartford", "CT"
  ],
  [
    "Serafima Babatunde", "Example Inc.", "Tampa", "FL"
  ],
  [
    "Gaston Festus", "Example Inc.", "Tampa", "FL"
  ]
];

const useStyles = makeStyles((theme) => ({
  root: {
    '& > *': {
      margin: theme.spacing(1)
    }
  }
}));

export default function Profiles() {
  const classes = useStyles();

  const [msg, setMsg] = useState("waiting for message...");
  const [squeaks, setSqueaks] = useState([]);
  const [signingProfiles, setSigningProfiles] = useState([]);
  const history = useHistory();

  const getMsg = () => {
    console.log("called getMsg");

    var helloRequest = new HelloRequest()
    helloRequest.setName('World');

    client.sayHello(helloRequest, {}, (err, response) => {
      console.log(response.getMessage());
      setMsg(response.getMessage())
    });
  };
  const getSqueaks = () => {
    console.log("called getSqueaks");

    var getSqueaksRequest = new GetFollowedSqueakDisplaysRequest()

    client.getFollowedSqueakDisplays(getSqueaksRequest, {}, (err, response) => {
      console.log(response);
      console.log(response.getSqueakDisplayEntriesList());
      // console.log(response.getSqueakDisplayEntriesList(),length);
      setSqueaks(response.getSqueakDisplayEntriesList())
    });
  };
  const getLndInfo = () => {
    console.log("called getLndInfo");

    var getInfoRequest = new GetInfoRequest()

    client.lndGetInfo(getInfoRequest, {}, (err, response) => {
      console.log(response);
    });
  };
  const getSigningProfiles = () => {
    console.log("called getSigningProfiles");

    var getSigningProfilesRequest = new GetSigningProfilesRequest()

    client.getSigningProfiles(getSigningProfilesRequest, {}, (err, response) => {
      console.log(response);
      var signingProfileRows = response.getSqueakProfilesList().map(p => [p.getProfileName(), p.getAddress(), p.getFollowing().toString(), p.getSharing().toString()]);
      setSigningProfiles(signingProfileRows);
    });
  };
  useEffect(() => {
    getMsg()
  }, []);
  useEffect(() => {
    getSqueaks()
  }, []);
  useEffect(() => {
    getLndInfo()
  }, []);
  useEffect(() => {
    getSigningProfiles()
  }, []);

  return (<> < PageTitle title = "Profiles" /> <Grid container="container" spacing={4}>
    <Grid item="item" xs={12}>
      <div className={classes.root}>
        <Button variant="contained" onClick={() => {
            alert('clicked')
          }}>Create Signing Profile</Button>
        <Button variant="contained" onClick={() => {
            alert('clicked')
          }}>Add contact</Button>
      </div>
    </Grid>
    <Grid item="item" xs={12}>
      <MUIDataTable title="Profile List" data={signingProfiles} columns={["Name", "Address", "Following", "Sharing"]} options={{
          filter: false,
          print: false,
          viewColumns: false,
          selectableRows: "none",
          onRowClick: rowData => {
            console.log(rowData);
            var address = rowData[1];
            console.log(address);
            history.push("/app/squeakaddress/" + address);
          }
        }}/>
    </Grid>
  </Grid> < />);
}
