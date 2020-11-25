import React from "react";
import {useHistory} from "react-router-dom";

import Card from '@material-ui/core/Card';
import Button from '@material-ui/core/Button';
import CardHeader from "@material-ui/core/CardHeader";

// icons
import RecordVoiceOverIcon from '@material-ui/icons/RecordVoiceOver';

import useStyles from "../../pages/wallet/styles";


export default function LightningPeerListItem({
  peer,
  ...props
}) {
  const classes = useStyles({
    clickable: true,
  });

  const history = useHistory();

  const onPeerClick = (event) => {
    event.preventDefault();
    console.log("Handling peer click...");
    goToLightningNodePage();
  }

  const goToLightningNodePage = () => {
    const pubkey = peer.getPubKey();
    const host = getPeerHost();
    const port = getPeerPort();
    history.push("/app/lightningnode/" + pubkey + "/" + host + "/" + port);
  };

  const getPeerHost = () => {
    const address = peer.getAddress();
    if (address == null) {
      return null;
    }
    const pieces = address.split(":");
    return pieces[0];
  }

  const getPeerPort = () => {
    const address = peer.getAddress();
    if (address == null) {
      return null;
    }
    const pieces = address.split(":");
    if (pieces.length < 2) {
      return null;
    }
    return pieces[1];
  }

  return (
     <Card
        className={classes.root}
        onClick={onPeerClick}
     >
       <CardHeader
          avatar={<RecordVoiceOverIcon/>}
          title={`Pubkey: ${peer.getPubKey()}`}
          subheader={`Address: ${peer.getAddress()}`}
          // action={<Button size="small">View Peer</Button>}
       />
     </Card>
  )
}
